import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date
import time
from functools import wraps

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
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Rate limiting decorator
def rate_limit(max_calls=1, time_window=1.5):
    """Decorator to rate limit function calls"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            if not hasattr(wrapper, 'last_called'):
                wrapper.last_called = 0
            
            time_since_last_call = current_time - wrapper.last_called
            if time_since_last_call < time_window:
                time.sleep(time_window - time_since_last_call)
            
            wrapper.last_called = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Load credentials from Streamlit secrets
@st.cache_resource
def init_connection():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPE
    )
    client = gspread.authorize(credentials)
    return client

# Cached data fetching functions with rate limiting
@st.cache_data(ttl=30)  # Cache for 30 seconds
@rate_limit(max_calls=1, time_window=2.0)
def get_users_data():
    """Get users data with caching and rate limiting"""
    try:
        client = init_connection()
        users_sheet = client.open("twi_users").sheet1
        return users_sheet.get_all_records()
    except Exception as e:
        st.error(f"Error fetching users data: {str(e)}")
        return []

@st.cache_data(ttl=15)  # Cache for 15 seconds (shorter for dataset updates)
@rate_limit(max_calls=1, time_window=2.0)
def get_dataset_data():
    """Get dataset data with caching and rate limiting"""
    try:
        client = init_connection()
        dataset_sheet = client.open("twi_dataset").sheet1
        return dataset_sheet.get_all_records()
    except Exception as e:
        st.error(f"Error fetching dataset: {str(e)}")
        return []

# Rate-limited write operations
@rate_limit(max_calls=1, time_window=2.0)
def add_user_data(user_data):
    """Add user data with rate limiting"""
    try:
        client = init_connection()
        users_sheet = client.open("twi_users").sheet1
        users_sheet.append_row(user_data)
        # Clear cache after write
        get_users_data.clear()
        return True
    except Exception as e:
        st.error(f"Error adding user: {str(e)}")
        return False

@rate_limit(max_calls=1, time_window=2.0)
def add_dataset_entry(entry_data):
    """Add dataset entry with rate limiting"""
    try:
        client = init_connection()
        dataset_sheet = client.open("twi_dataset").sheet1
        dataset_sheet.append_row(entry_data)
        # Clear cache after write
        get_dataset_data.clear()
        return True
    except Exception as e:
        st.error(f"Error adding dataset entry: {str(e)}")
        return False

@rate_limit(max_calls=1, time_window=2.0)
def delete_user_by_username(username_to_delete):
    """Delete user with rate limiting"""
    try:
        client = init_connection()
        users_sheet = client.open("twi_users").sheet1
        users_list = users_sheet.get_all_records()
        
        for i, user in enumerate(users_list, start=2):  # row 2 = first user
            if str(user.get("username", "")).lower() == username_to_delete.lower():
                users_sheet.delete_rows(i)
                get_users_data.clear()  # Clear cache
                return True
        return False
    except Exception as e:
        st.error(f"Error deleting user: {str(e)}")
        return False

@rate_limit(max_calls=1, time_window=2.0)
def delete_contributions_by_username(username):
    """Delete all contributions by username with rate limiting"""
    try:
        client = init_connection()
        dataset_sheet = client.open("twi_dataset").sheet1
        dataset_rows = dataset_sheet.get_all_records()
        
        rows_to_delete = [i for i, row in enumerate(dataset_rows, start=2) 
                         if str(row.get("username", "")).lower() == username.lower()]

        for row_index in reversed(rows_to_delete):  # delete bottom-to-top
            dataset_sheet.delete_rows(row_index)
            time.sleep(0.5)  # Small delay between deletions
        
        get_dataset_data.clear()  # Clear cache
        return len(rows_to_delete)
    except Exception as e:
        st.error(f"Error deleting contributions: {str(e)}")
        return 0

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
        
        # Get data using cached functions
        with st.spinner("Loading data..."):
            users = get_users_data()
            dataset = get_dataset_data()
        
        st.header("Twi-English Dataset")
        if dataset:
            df = pd.DataFrame(dataset)
            st.dataframe(df)
        else:
            st.warning("No dataset entries found or error loading data.")
        
        st.header("All users")
        if users:
            dff = pd.DataFrame(users)
            st.dataframe(dff)
        else:
            st.warning("No users found or error loading data.")
        
        # Admin Statistics
        st.header("Dataset Statistics")
        total_entries = len(dataset) if dataset else 0
        total_users = len(users) if users else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Entries", total_entries)
        with col2:
            st.metric("Total Users", total_users)
        with col3:
            if total_users > 1:
                avg_entries = total_entries / max(total_users - 1, 1)
                st.metric("Avg Entries per User", f"{avg_entries:.1f}")
            else:
                st.metric("Avg Entries per User", "0.0")
        
        # 🔹 Contribution statistics
        if dataset and len(dataset) > 0:
            df = pd.DataFrame(dataset)
            if "username" in df.columns:
                st.subheader("User Contribution Statistics")
                username_counts = df["username"].value_counts().reset_index()
                username_counts.columns = ["Username", "Entries Count"]

                st.dataframe(username_counts)
                st.bar_chart(username_counts.set_index("Username"))
        
        # 🔹 Delete a user from USERS sheet
        st.subheader("Manage Users")
        if users and len(users) > 0:
            dff = pd.DataFrame(users)
            if "username" in dff.columns:
                user_to_delete = st.selectbox("Select user to delete", options=dff["username"].tolist())
                if st.button("Delete User"):
                    with st.spinner("Deleting user..."):
                        if delete_user_by_username(user_to_delete):
                            st.success(f"User '{user_to_delete}' deleted successfully!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("Failed to delete user.")

        # 🔹 Delete all contributions by a username
        st.subheader("Manage Contributions")
        if dataset and len(dataset) > 0:
            df = pd.DataFrame(dataset)
            if "username" in df.columns:
                contrib_user = st.selectbox("Select user to delete contributions", 
                                          options=df["username"].unique().tolist())
                if st.button("Delete All Contributions"):
                    with st.spinner("Deleting contributions..."):
                        deleted_count = delete_contributions_by_username(contrib_user)
                        if deleted_count > 0:
                            st.success(f"Deleted {deleted_count} contributions by '{contrib_user}'!")
                        else:
                            st.info(f"No contributions found for user '{contrib_user}'")
                        time.sleep(2)
                        st.rerun()
            
    # Regular User Data Collection Page    
    else:
        st.header(f"Welcome, {st.session_state.username}!")
        
        # Get fresh data with caching
        with st.spinner("Loading your statistics..."):
            dataset = get_dataset_data()
        
        # Case-insensitive comparison for user entries
        user_entries = [row for row in dataset if str(row.get('username', '')).lower() == st.session_state.username.lower()]
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
        
        # Show encouragement message for new users
        if entry_count == 0:
            st.info("You haven't made any contributions yet. Use the form below to add your first entry!")
        
        # Data Collection Form
        st.subheader("Data Collection Form")
        
        with st.form("data_collection", clear_on_submit=True):
            select_date = st.date_input("Date", date.today())
            twi = st.text_area("Enter Twi Sentence (best option minimum 10 words and maximum 15 words)", 
                             height=100, placeholder="Type your Twi sentence here...")
            english = st.text_area("Enter English Translation", 
                                 height=100, placeholder="Type the English translation here...")
            
            submitted = st.form_submit_button("Submit Data", use_container_width=True)
            
            if submitted:
                if not twi.strip() or not english.strip():
                    st.error("Please fill in both Twi sentence and English translation!")
                else:
                    # Check for duplicates
                    duplicate_found = False
                    for row in dataset:
                        if (str(row.get('ewe', '')).strip().lower() == twi.strip().lower() and 
                            str(row.get('english', '')).strip().lower() == english.strip().lower() and
                            str(row.get('username', '')).lower() == st.session_state.username.lower()):
                            duplicate_found = True
                            break
                    
                    if duplicate_found:
                        st.warning("This translation pair already exists in your submissions!")
                    else:
                        with st.spinner("Submitting your entry..."):
                            entry_data = [
                                select_date.strftime("%Y-%m-%d"),
                                twi.strip(),
                                english.strip(),
                                st.session_state.username,
                            ]
                            
                            if add_dataset_entry(entry_data):
                                st.success("Data submitted successfully!")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Failed to submit data. Please try again.")

else:
    # Login/Registration Page
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab2:
        st.subheader("Create New Account")
        with st.form("Registration", clear_on_submit=True):
            name = st.text_input("Enter Full Name")
            username = st.text_input("Enter Username/Nickname")
            password = st.text_input("Enter Password", type="password") 
            repassword = st.text_input("Repeat Password", type="password")
            momo_contact = st.text_input("Enter Momo Number")
            momo_name = st.text_input("Enter Momo Account Name (for payment and verification)")
            call_contact = st.text_input("Enter Contact (for calls)")
            email = st.text_input("Enter Email")
            
            if st.form_submit_button("Register"):
                name = name.strip()
                username = username.strip()
                password = password.strip()
                repassword = repassword.strip()
                momo_contact = momo_contact.strip()
                momo_name = momo_name.strip()
                call_contact = call_contact.strip()
                email = email.strip()
                
                if not name or not username or not password:
                    st.error("Please fill in all fields!")
                elif password != repassword:
                    st.error("Your passwords do not match")
                elif len(password) < 4:
                    st.error("Password must be at least 4 characters long")
                else:
                    with st.spinner("Checking username availability..."):
                        users = get_users_data()
                        username_exists = any(str(user.get('username', '')).lower() == username.lower() for user in users)
                        
                        if username_exists:
                            st.error("Username already exists! Please choose a different one.")
                        else:
                            with st.spinner("Creating account..."):
                                user_data = [name, momo_contact, call_contact, username, password, email, momo_name]
                                if add_user_data(user_data):
                                    st.success("Registration Successful! You can now login.")
                                else:
                                    st.error("Registration failed. Please try again.")
    
    with tab1:
        st.subheader("Login to Your Account")
        with st.form("Login"):
            username100 = st.text_input("Enter Username/Nickname")
            password100 = st.text_input("Enter Password", type="password")
            
            if st.form_submit_button("Login"):
                username100 = username100.strip()
                password100 = password100.strip()
                
                if not username100 or not password100:
                    st.error("Please enter both username and password")
                else:
                    if username100.lower() == "admin" and password100 == "1345":
                        st.session_state.logged_in = True
                        st.session_state.username = "admin"
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        with st.spinner("Verifying credentials..."):
                            users = get_users_data()
                            found = False
                            
                            for user in users:
                                if (str(user.get("username", "")).lower() == username100.lower() and 
                                    str(user.get("password", "")) == password100):
                                    found = True
                                    st.session_state.logged_in = True
                                    st.session_state.username = str(user.get("username", ""))
                                    st.session_state.is_admin = False
                                    st.rerun()
                                    break
                            
                            if not found:
                                st.error("Wrong login details. Please try again.")
