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
            background-color: #ffffff;   /* White background */
            color: black;               /* Black text */
        }
        .stTextInput label, .stTextArea label, .stDateInput label {
            color: black !important;    /* Black form labels */
        }
        .stDataFrame, .stMarkdown, .stHeader, .stSubheader, .stRadio, .stSelectbox label {
            color: black !important;    /* Black text everywhere */
        }
        .css-1d391kg, .css-1v3fvcr {   /* Sidebar / container fix */
            background-color: #f9f9f9 !important;  /* Light gray sidebar */
        }

        /* ✅ Button Styling */
        div.stButton > button, form button {
            color: white !important;       /* White text */
            background-color: #007acc !important; /* Blue background */
            font-weight: bold;
            border-radius: 8px;            /* Rounded corners */
            padding: 0.4em 1em;
            border: none;
        }

        /* Hover effect */
        div.stButton > button:hover, form button:hover {
            background-color: #005fa3 !important;  /* Darker blue */
            color: white !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Define scope
#SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Load credentials from Streamlit secrets
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
client1=clients.open("ewe_dataset_users").sheet1
client2 = clients.open("ewe_dataset").sheet1

# Initialize session state for login status
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("Twi Dataset Hub")

# Check if user is logged in
if st.session_state.logged_in:
    # Admin Dashboard
    if st.session_state.is_admin:
        st.header("Admin Dashboard")
        
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.is_admin = False 
            st.rerun()
        
        # Get data and display (moved outside the logout button logic)
        users = client1.get_all_records()
        dataset = client2.get_all_records()
        
        st.header("Twi-English Dataset")
        df = pd.DataFrame(dataset)
        st.dataframe(df)
        
        st.header("All users")
        dff = pd.DataFrame(users)
        st.dataframe(dff)
        
        # Admin Statistics
        st.header("Dataset Statistics")
        total_entries = len(dataset)
        total_users = len(users)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Entries", total_entries)
        with col2:
            st.metric("Total Users", total_users)
        with col3:
            avg_entries = total_entries / max(total_users - 1, 1)  # Subtract 1 for admin
            st.metric("Avg Entries per User", f"{avg_entries:.1f}")
        # 🔹 Contribution statistics
        if not df.empty and "username" in df.columns:
            st.subheader("User Contribution Statistics")
            username_counts = df["username"].value_counts().reset_index()
            username_counts.columns = ["Username", "Entries Count"]

            st.dataframe(username_counts)
            st.bar_chart(username_counts.set_index("Username"))
        # 🔹 Delete a user from USERS sheet
        st.subheader("Manage Users")
        if not dff.empty and "username" in dff.columns:
            user_to_delete = st.selectbox("Select user to delete", options=dff["username"].tolist())
            if st.button("Delete User"):
                users_list = client1.get_all_records()
                for i, user in enumerate(users_list, start=2):  # row 2 = first user
                    if user["username"] == user_to_delete:
                        client1.delete_rows(i)
                        st.success(f"User '{user_to_delete}' deleted successfully!")
                        st.rerun()

        # 🔹 Delete all contributions by a username
        st.subheader("Manage Contributions")
        if not df.empty and "username" in df.columns:
            contrib_user = st.selectbox("Select user to delete contributions", options=df["username"].unique().tolist())
            if st.button("Delete All Contributions"):
                dataset_rows = client2.get_all_records()
                rows_to_delete = [i for i, row in enumerate(dataset_rows, start=2) if row["username"] == contrib_user]

                for row_index in reversed(rows_to_delete):  # delete bottom-to-top
                    client2.delete_rows(row_index)
                    st.success(f"All contributions by '{contrib_user}' deleted successfully!")
            
    # Regular User Data Collection Page    
    else:
        st.header(f"Welcome, {st.session_state.username}!")
        
        # Get user's entry count
        dataset = client2.get_all_records()
        user_entries = [row for row in dataset if str(row.get('username', '')) == st.session_state.username]
        entry_count = len(user_entries)
        
        # Display user statistics - only total entries
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Your Total Entries", entry_count)
        with col2:
            if st.button("Logout"):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.is_admin = False
                st.rerun()
        
        # Data Collection Form
        st.subheader("Data Collection Form")
        
        # Use the simpler clear_on_submit approach
        with st.form("data_collection", clear_on_submit=True):
            # Add your data collection fields here
            select_date =  st.date_input("Date", date.today())
            ewe = st.text_area("Enter Twi Sentence (best option minimum 10 words and maximum 15 words)", height=100, placeholder="Type your Ewe sentence here...")
            english = st.text_area("Enter English Translation", height=100, placeholder="Type the English translation here...")
            
            submitted = st.form_submit_button("Submit Data", use_container_width=True)
            
            if submitted:
                # Double check for empty fields (extra security)
                if not ewe.strip() or not english.strip():
                    st.error("Please fill in both Ewe sentence and English translation!")
                else:
                    # Check for duplicates (optional - compares with existing data)
                    duplicate_found = False
                    
                    for row in dataset:
                        if (str(row.get('ewe', '')).strip().lower() == ewe.strip().lower() and 
                            str(row.get('english', '')).strip().lower() == english.strip().lower() and
                            str(row.get('username', '')) == st.session_state.username):
                            duplicate_found = True
                            break
                    
                    if duplicate_found:
                        st.warning("This translation pair already exists in your submissions!")
                    else:
                        # Save data to Google Sheets (without date)
                        client2.append_row([select_date.strftime("%Y-%m-%d"),
                            ewe.strip(),
                            english.strip(),
                            st.session_state.username,
                        ])
                        st.success("Data submitted successfully!")
                        st.balloons()  # Fun visual feedback
                        st.rerun()  # Refresh to update the entry count
        


else:
    # Login/Registration Page
    tab1, tab2= st.tabs(["Login", "Register"])
    
    with tab2:
        st.subheader("Create New Account")
        with st.form("Registration", clear_on_submit=True):
            users= client1.get_all_records()
            name = st.text_input("Enter Full Name")
            username= st.text_input("Enter Username/Nickname")
            password = st.text_input("Enter Password", type= "password") 
            repassword = st.text_input("Repeat Password", type="password")
            momo_contact= st.text_input("Enter Momo Number")
            momo_name= st.text_input("Enter Momo Account Name (for payment and verification)")
            call_contact= st.text_input("Enter Contact (for calls)")
            email=st.text_input("Enter Email")
            
            if st.form_submit_button("Register"):
                name = name.strip()
                username = username.strip()
                password = password.strip()
                repassword = repassword.strip()
                momo_contact=momo_contact.strip()
                momo_name= momo_name.strip()
                call_contact= call_contact.strip()
                email=email.strip()
                
                if not name or not username or not password:
                    st.error("Please fill in all fields!")
                elif password != repassword:
                    st.error("Your passwords do not match")
                elif len(password) < 4:
                    st.error("Password must be at least 4 characters long")
                else:
                    # Check if username already exists
                    username_exists = any(str(user.get('username', '')).lower() == username.lower() for user in users)
                    if username_exists:
                        st.error("Username already exists! Please choose a different one.")
                    else:
                        client1.append_row([name, momo_contact, call_contact, username, password, email, momo_name])
                        st.success("Registration Successful! You can now login.")
    
    with tab1:
        st.subheader("Login to Your Account")
        with st.form("Login"):
            users= client1.get_all_records()
            username100 = st.text_input("Enter Username/Nickname")
            password100= st.text_input("Enter Password", type= "password")
            
            if st.form_submit_button("Login"):
                username100 = username100.strip().lower()
                password100 = password100.strip()
                
                if not username100 or not password100:
                    st.error("Please enter both username and password")
                else:
                    found = False
                    if username100 == "admin" and password100 == "1345":
                        st.session_state.logged_in = True
                        st.session_state.username = "admin"
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        for user in users:
                            if str(user.get("username", "")).lower() == username100 and str(user.get("password", "")) == password100:
                                found = True
                                st.session_state.logged_in = True
                                st.session_state.username = str(user.get("username", ""))
                                st.session_state.is_admin = False
                                st.rerun()
                                break
                        if not found:
                            st.error("Wrong login details. Please try again.")




