import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date

# --- Light Theme CSS ---
st.markdown(
    """
    <style>
        .stApp {
            background-color: #ffffff;
            color: black;
        }
        .stTextInput label, .stTextArea label, .stDateInput label {
            color: black !important;
        }
        .stDataFrame, .stMarkdown, .stHeader, .stSubheader, .stRadio, .stSelectbox label {
            color: black !important;
        }
        .css-1d391kg, .css-1v3fvcr {
            background-color: #f9f9f9 !important;
        }
        div.stButton > button, form button {
            color: white !important;
            background-color: #007acc !important;
            font-weight: bold;
            border-radius: 8px;
            padding: 0.4em 1em;
            border: none;
        }
        div.stButton > button:hover, form button:hover {
            background-color: #005fa3 !important;
            color: white !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

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

# Session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("📖 Twi Dataset Hub")

# ----------------- ADMIN DASHBOARD -----------------
if st.session_state.logged_in and st.session_state.is_admin:
    st.header("🛠️ Admin Dashboard")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.rerun()

    users = client1.get_all_records()
    dataset = client2.get_all_records()

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
            st.success(f"All contributions from '{contrib_user}' deleted")
            st.rerun()

# ----------------- USER DASHBOARD -----------------
elif st.session_state.logged_in and not st.session_state.is_admin:
    dataset = client2.get_all_records()
    user_entries = [row for row in dataset if str(row.get('username','')) == st.session_state.username]
    entry_count = len(user_entries)

    # Header with stats + logout on SAME LINE
    col1, col2 = st.columns([3,1])
    with col1:
        st.subheader(f"👋 Welcome, {st.session_state.username}! | 📊 Total Entries: {entry_count}")
    with col2:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.is_admin = False
            st.rerun()

    # Data entry form
    st.subheader("📝 Add New Entry")
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
                    str(row.get('english','')).strip().lower() == english.strip().lower() and
                    str(row.get('username','')) == st.session_state.username
                    for row in dataset
                )
                if duplicate_found:
                    st.warning("⚠️ This translation pair already exists in your submissions.")
                else:
                    client2.append_row([
                        select_date.strftime("%Y-%m-%d"),
                        twi.strip(),
                        english.strip(),
                        st.session_state.username
                    ])
                    st.success("✅ Entry submitted successfully!")
                    st.balloons()
                    st.rerun()

# ----------------- LOGIN / REGISTER -----------------
else:
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])

    with tab2:
        st.subheader("Create New Account")
        with st.form("register_form", clear_on_submit=True):
            users = client1.get_all_records()
            name = st.text_input("Full Name")
            username = st.text_input("Username/Nickname")
            password = st.text_input("Password", type="password")
            repassword = st.text_input("Repeat Password", type="password")

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
                    client1.append_row([username.strip(), password.strip(), name.strip()])
                    st.success("🎉 Registration successful! Please login.")

    with tab1:
        st.subheader("Login to Your Account")
        with st.form("login_form"):
            users = client1.get_all_records()
            username_in = st.text_input("Username/Nickname")
            password_in = st.text_input("Password", type="password")

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

