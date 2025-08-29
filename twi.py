import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date




# Google Sheets setup
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def init_connection():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPE
    )
    client = gspread.authorize(credentials)
    return client

# Initialize connection
clients = init_connection()
client1 = clients.open("twi_users").sheet1
client2 = clients.open("twi_dataset").sheet1



# -----------------------------
# Caching Helpers (to avoid hitting API quota)
# -----------------------------
@st.cache_data(ttl=60)  # cache results for 60 seconds
def load_users():
    return client1.get_all_records()

@st.cache_data(ttl=60)
def load_dataset():
    return client2.get_all_records()


# Session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'uploaded_excel' not in st.session_state:   # 🔹 track uploaded excel
    st.session_state.uploaded_excel = None

st.title("📖 Twi Dataset Hub")

# ----------------- ADMIN DASHBOARD -----------------
if st.session_state.logged_in and st.session_state.is_admin:
    st.header("🛠️ Admin Dashboard")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.rerun()

    users = load_users()
    dataset = load_dataset()

    st.subheader("📖 Twi-English Dataset")
    df = pd.DataFrame(dataset)
    st.dataframe(df)

    st.subheader("👥 All Users")
    dff = pd.DataFrame(users)
    st.dataframe(dff)

    st.subheader("📊 Dataset Statistics")
    total_entries = len(dataset)
    total_users = len(users)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Entries", total_entries)
    col2.metric("Total Users", total_users)
    col3.metric("Avg Entries/User", f"{total_entries / max(total_users-1,1):.1f}")

    if not df.empty and "username" in df.columns:
        st.subheader("📌 User Contributions")
        username_counts = df["username"].value_counts().reset_index()
        username_counts.columns = ["Username", "Entries Count"]
        st.dataframe(username_counts)
        st.bar_chart(username_counts.set_index("Username"))

    # User & contribution deletion
    st.subheader("🗑️ Manage Users")
    if not dff.empty and "username" in dff.columns:
        user_to_delete = st.selectbox("Select user to delete", options=dff["username"].tolist())
        if st.button("Delete User"):
            for i, user in enumerate(client1.get_all_records(), start=2):
                if user["username"] == user_to_delete:
                    client1.delete_rows(i)
                    st.cache_data.clear()  # 🔄 clear cache after mutation
                    st.success(f"Deleted user '{user_to_delete}'")
                    st.rerun()

    st.subheader("🗑️ Manage Contributions")
    if not df.empty and "username" in df.columns:
        contrib_user = st.selectbox("Select user to delete contributions", options=df["username"].unique().tolist())
        if st.button("Delete Contributions"):
            dataset_rows = client2.get_all_records()
            rows_to_delete = [i for i, row in enumerate(dataset_rows, start=2) if row["username"] == contrib_user]
            for row_index in reversed(rows_to_delete):
                client2.delete_rows(row_index)
            st.cache_data.clear()  # 🔄 clear cache after mutation
            st.success(f"All contributions from '{contrib_user}' deleted")
            st.rerun()

# ----------------- USER DASHBOARD -----------------
elif st.session_state.logged_in and not st.session_state.is_admin:
    dataset = load_dataset()
    df = pd.DataFrame(dataset)

    # 🔹 Count current user's entries
    if not df.empty and "username" in df.columns:
        user_entries = df[df["username"] == st.session_state.username]
        entry_count = len(user_entries)
    else:
        entry_count = 0

    # Header with stats + logout on SAME LINE
    col1, col2 = st.columns([3,1])
    with col1:
        st.subheader(f"👋 Welcome, {st.session_state.username} 🤗 | Entries = {entry_count}")
    with col2:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.is_admin = False
            st.rerun()

    # Tabs for entry methods
    st.subheader("📝 Data Collection Form")
    tab_manual, tab_excel = st.tabs(["✍️ Manual Entry", "📂 Upload Excel"])

    with tab_manual:
        with st.form("data_form", clear_on_submit=True):
            select_date = st.date_input("Date", date.today())
            twi = st.text_area("Enter Twi Sentence (10–15 words preferred)", height=100, placeholder="Type the Twi sentence here...")
            english = st.text_area("Enter English Translation", height=100, placeholder="Type the English translation here...")

            submitted = st.form_submit_button("Submit Data", use_container_width=True)
            if submitted:
                if not twi.strip() or not english.strip():
                    st.error("❌ Please fill in both fields!")
                else:
                    duplicate_found = any(
                        str(row.get('twi','')).strip().lower() == twi.strip().lower() and
                        str(row.get('english','')).strip().lower() == english.strip().lower()
                        for row in dataset
                    )
                    if duplicate_found:
                        st.warning("⚠️ This translation pair already exists in the dataset.")
                    else:
                        client2.append_row([
                            select_date.strftime("%Y-%m-%d"),
                            twi.strip(),
                            english.strip(),
                            st.session_state.username
                        ])
                        st.cache_data.clear()  # 🔄 clear cache after mutation
                        st.success("✅ Entry submitted successfully!")
                        st.balloons()
                        st.rerun()

    with tab_excel:
        st.session_state.uploaded_excel = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])  # 🔹 track file
        if st.session_state.uploaded_excel:
            try:
                excel_df = pd.read_excel(st.session_state.uploaded_excel)
    
                # 🔹 Force first col = twi, second col = english (ignore column names)
                if excel_df.shape[1] < 2:
                    st.error("❌ Excel file must contain at least two columns (Twi and English).")
                else:
                    excel_df = excel_df.iloc[:, :2]  # Take only first two columns
                    excel_df.columns = ["twi", "english"]  # Rename to standard
    
                    st.write("✅ Preview of uploaded file (first two columns as Twi & English):")
                    st.dataframe(excel_df.head())
    
                    if st.button("Insert All Rows into Google Sheet"):
                        today_str = date.today().strftime("%Y-%m-%d")
                        rows_to_add = []
                        duplicates_skipped = 0
    
                        for _, row in excel_df.iterrows():
                            twi_text = str(row["twi"]).strip()
                            eng_text = str(row["english"]).strip()
                            if not twi_text or not eng_text:
                                continue
    
                            # Check duplication against existing dataset
                            duplicate_found = any(
                                str(r.get('twi','')).strip().lower() == twi_text.lower() and
                                str(r.get('english','')).strip().lower() == eng_text.lower()
                                for r in dataset
                            )
    
                            if duplicate_found:
                                duplicates_skipped += 1
                                continue
                            rows_to_add.append([today_str, twi_text, eng_text, st.session_state.username])
    
                        if rows_to_add:
                            client2.append_rows(rows_to_add)
                            st.cache_data.clear()  # 🔄 clear cache after mutation
                            st.session_state.uploaded_excel = None  # 🔹 clear file so preview disappears
                            st.success(f"🎉 Inserted {len(rows_to_add)} new rows! 🚫 Skipped {duplicates_skipped} duplicates.")
                            st.rerun()
                        else:
                            st.warning("⚠️The entries already exist.")
            except Exception as e:
                st.error(f"❌ Error reading Excel file: {e}")

# ----------------- LOGIN / REGISTER -----------------
else:
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])

    with tab2:
        st.subheader("Create New Account")
        with st.form("register_form", clear_on_submit=True):
            users = load_users()
            name = st.text_input("Full Name", placeholder="Enter Full Name")
            username = st.text_input("Username/Nickname", placeholder= "Enter Username/Nickname")
            password = st.text_input("Password", type="password", placeholder="Enter Password")
            repassword = st.text_input("Repeat Password", type="password", placeholder="Repeat Password")
            momo_contact= st.text_input("Payment Phone Number", placeholder= "Enter Phone Number for Cash Transfer")
            momo_contact_1= st.text_input("Network Provider of Payment Phone Number", placeholder= "Enter the Network provider (Telecel Cash/MoMo/AirtelTigo Cash)")
            momo_name=st.text_input("Account Name", placeholder= "Enter Account Name of the Payment Phone Number")
            call_contact= st.text_input("Call Contact", placeholder= "Enter Call Contact")
            email= st.text_input("Email", placeholder= "Enter Email")

            if st.form_submit_button("Register"):
                if not name or not username or not password:
                    st.error("❌ Please fill all fields")
                elif password != repassword:
                    st.error("❌ Passwords do not match")
                elif len(password) < 4:
                    st.error("❌ Password must be at least 4 characters")
                elif any(str(user.get("username","")).lower() == username.lower() for user in users):
                    st.error("❌ Username already exists")
                else:
                    client1.append_row([name.strip(), momo_contact.strip(), call_contact.strip(), username.strip(), password.strip(), email.strip(), momo_name.strip(), momo.contact_1.strip()])
                    st.cache_data.clear()  # 🔄 clear cache after mutation
                    st.success("🎉 Registration successful! Please login.")

    with tab1:
        st.subheader("Login to Your Account")
        with st.form("login_form"):
            users = load_users()
            username_in = st.text_input("Username/Nickname", placeholder="Enter Username/Nickname")
            password_in = st.text_input("Password", type="password", placeholder="Enter Password")

            if st.form_submit_button("Login"):
                username_in = username_in.strip().lower()
                password_in = password_in.strip()

                if not username_in or not password_in:
                    st.error("❌ Enter both username and password")
                elif username_in == "admin" and password_in == "1345":
                    st.session_state.logged_in = True
                    st.session_state.username = "admin"
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    found = False
                    for user in users:
                        if str(user.get("username","")).lower() == username_in and str(user.get("password","")) == password_in:
                            found = True
                            st.session_state.logged_in = True
                            st.session_state.username = str(user.get("username",""))
                            st.session_state.is_admin = False
                            st.rerun()
                    if not found:
                        st.error("❌ Wrong login details")




