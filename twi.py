import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date
import time
from functools import wraps

# -----------------------------
# Session State
# -----------------------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

st.title("📖 Twi Dataset Hub")

# -----------------------------
# Excel Processing Functions
# -----------------------------
def process_excel_file(uploaded_file, username):
    """Read Excel and let user select Twi/English columns"""
    try:
        df = pd.read_excel(uploaded_file)
        st.subheader("📊 Preview of uploaded file")
        st.dataframe(df.head())

        st.subheader("🎯 Column Mapping")
        columns = df.columns.tolist()
        twi_column = st.selectbox("Select column containing Twi/Ewe:", columns, key=f"twi_col_{username}")
        eng_column = st.selectbox("Select column containing English:", columns, key=f"eng_col_{username}")

        has_date_column = st.checkbox("File has Date column?", key=f"date_chk_{username}")
        date_column = None
        if has_date_column:
            date_column = st.selectbox("Select Date column:", columns, key=f"date_col_{username}")

        return df, twi_column, eng_column, date_column
    except Exception as e:
        st.error(f"❌ Error reading Excel file: {str(e)}")
        return None, None, None, None

def upload_to_sheets(df, twi_col, eng_col, date_col, username):
    """Upload valid rows to Google Sheets"""
    try:
        upload_data = []
        today = date.today().strftime("%Y-%m-%d")

        for _, row in df.iterrows():
            twi_text = str(row[twi_col]).strip() if pd.notna(row[twi_col]) else ""
            eng_text = str(row[eng_col]).strip() if pd.notna(row[eng_col]) else ""
            if not twi_text or not eng_text or twi_text.lower() == "nan" or eng_text.lower() == "nan":
                continue

            if date_col and pd.notna(row[date_col]):
                try:
                    entry_date = pd.to_datetime(row[date_col]).strftime("%Y-%m-%d")
                except:
                    entry_date = today
            else:
                entry_date = today

            upload_data.append([entry_date, twi_text, eng_text, username])

        # Upload to Sheets
        for row in upload_data:
            client2.append_row(row)

        return len(upload_data), len(df) - len(upload_data)
    except Exception as e:
        st.error(f"❌ Upload failed: {str(e)}")
        return 0, 0

# -----------------------------
# ADMIN DASHBOARD
# -----------------------------
if st.session_state.is_admin:
    st.header("🛠️ Admin Dashboard")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.rerun()

    users = client1.get_all_records()
    dataset = client2.get_all_records()

    # Dataset view
    st.subheader("📖 Twi-English Dataset")
    df = pd.DataFrame(dataset)
    st.dataframe(df)

    # Users view with contribution counts
    st.subheader("👥 All Users with Contributions")
    dff = pd.DataFrame(users)

    if not dff.empty:
        # Count contributions
        contribution_counts = {}
        for row in dataset:
            user = row["username"].lower()
            contribution_counts[user] = contribution_counts.get(user, 0) + 1

        dff["contributions"] = dff["username"].apply(
            lambda u: contribution_counts.get(u.lower(), 0)
        )

        # Show users + contributions
        st.dataframe(dff)

        # Show total per contributor (summary view)
        st.subheader("📊 Contributions Summary")
        summary_df = dff[["username", "contributions"]].sort_values(by="contributions", ascending=False)
        st.table(summary_df)

        # Show grand total
        total_entries = len(dataset)
        st.info(f"📝 **Total Dataset Entries: {total_entries}**")

    # -----------------------------
    # Delete Options
    # -----------------------------
    st.subheader("🗑️ Manage Users & Contributions")
    usernames = [u["username"] for u in users if u["username"].lower() != "admin"]
    del_user = st.selectbox("Select user", usernames)

    # Delete only the user, keep contributions
    if st.button("Delete User Only"):
        all_users = client1.get_all_values()
        for i, row in enumerate(all_users):
            if row and row[0].lower() == del_user.lower():
                client1.delete_rows(i+1)
                break
        st.success(f"✅ Deleted user '{del_user}' but kept their contributions")
        st.rerun()

    # Delete only contributions, keep user
    if st.button("Delete Contributions Only"):
        all_data = client2.get_all_values()
        rows_to_delete = [i for i, row in enumerate(all_data) if len(row) > 3 and row[3].lower() == del_user.lower()]
        for offset, row_index in enumerate(rows_to_delete):
            client2.delete_rows(row_index + 1 - offset)
        st.success(f"✅ Deleted all contributions from '{del_user}' but kept the user")
        st.rerun()

    # Delete both user and contributions
    if st.button("Delete User & Contributions"):
        # Remove user
        all_users = client1.get_all_values()
        for i, row in enumerate(all_users):
            if row and row[0].lower() == del_user.lower():
                client1.delete_rows(i+1)
                break

        # Remove contributions
        all_data = client2.get_all_values()
        rows_to_delete = [i for i, row in enumerate(all_data) if len(row) > 3 and row[3].lower() == del_user.lower()]
        for offset, row_index in enumerate(rows_to_delete):
            client2.delete_rows(row_index + 1 - offset)

        st.success(f"✅ Deleted user '{del_user}' and all their contributions")
        st.rerun()

    # Upload Excel (admin bulk)
    st.subheader("📤 Bulk Upload (Excel)")
    admin_file = st.file_uploader("Upload Excel", type=['xlsx', 'xls'], key="admin_upload")
    if admin_file:
        df_preview, twi_col, eng_col, date_col = process_excel_file(admin_file, "admin")
        if df_preview is not None and twi_col and eng_col:
            if st.button("🚀 Upload to Google Sheets", key="admin_upload_btn"):
                uploaded, skipped = upload_to_sheets(df_preview, twi_col, eng_col, date_col, "admin")
                st.success(f"✅ Uploaded {uploaded} rows, skipped {skipped}")

# -----------------------------
# USER DASHBOARD
# -----------------------------
elif st.session_state.logged_in:
    st.header(f"👋 Welcome, {st.session_state.username}")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.rerun()

    # ✅ Show contribution count
    dataset = client2.get_all_records()
    my_count = sum(1 for row in dataset if row["username"].lower() == st.session_state.username.lower())
    st.info(f"📊 You have contributed **{my_count} entries** so far.")

    tab1, tab2 = st.tabs(["📝 Manual Entry", "📁 Excel Upload"])

    # Manual Entry
    with tab1:
        st.subheader("Manual Data Entry")
        with st.form("manual_form"):
            selected_date = st.date_input("Select date", value=date.today())
            twi = st.text_input("Enter Ewe Sentence")
            eng = st.text_area("Enter English Translation")
            if st.form_submit_button("Submit"):
                if twi and eng:
                    client2.append_row([selected_date.strftime("%Y-%m-%d"), twi, eng, st.session_state.username])
                    st.success("✅ Entry added!")
                else:
                    st.error("❌ Please fill in both fields")

    # Excel Upload
    with tab2:
        st.subheader("📤 Upload from Excel")
        user_file = st.file_uploader("Upload Excel", type=['xlsx', 'xls'], key="user_upload")
        if user_file:
            df_preview, twi_col, eng_col, date_col = process_excel_file(user_file, st.session_state.username)
            if df_preview is not None and twi_col and eng_col:
                if st.button("🚀 Upload to Google Sheets", key="user_upload_btn"):
                    uploaded, skipped = upload_to_sheets(df_preview, twi_col, eng_col, date_col, st.session_state.username)
                    st.success(f"✅ Uploaded {uploaded} rows, skipped {skipped}")

# -----------------------------
# LOGIN / REGISTER
# -----------------------------
else:
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])

    # Register
    with tab2:
        with st.form("register_form"):
            users = client1.get_all_records()
            name = st.text_input("Full Name").strip()
            username = st.text_input("Username").strip()
            password = st.text_input("Password", type="password").strip()
            repass = st.text_input("Repeat Password", type="password").strip()
            if st.form_submit_button("Register"):
                if not name or not username or not password:
                    st.error("❌ Fill all fields")
                elif password != repass:
                    st.error("❌ Passwords do not match")
                elif any(u["username"].lower() == username.lower() for u in users):
                    st.error("❌ Username exists")
                else:
                    client1.append_row([username, password, name])
                    st.success("🎉 Registered successfully! Please login.")

    # Login
    with tab1:
        with st.form("login_form"):
            users = client1.get_all_records()
            username_in = st.text_input("Username").strip().lower()
            password_in = st.text_input("Password", type="password").strip()
            if st.form_submit_button("Login"):
                if username_in == "admin" and password_in == "1345":
                    st.session_state.logged_in = True
                    st.session_state.username = "admin"
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    for user in users:
                        if user["username"].lower() == username_in and str(user["password"]) == password_in:
                            st.session_state.logged_in = True
                            st.session_state.username = username_in
                            st.session_state.is_admin = False
                            st.rerun()
                    st.error("❌ Wrong login details")
