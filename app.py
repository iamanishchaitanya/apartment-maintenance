import streamlit as st
import pandas as pd
from supabase import create_client

# Page Config
st.set_page_config(page_title="Apartment Maintenance Dashboard", page_icon="🏡", layout="wide")

# Initialize Supabase Connection using Streamlit secrets
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

st.title("🏡 Apartment Maintenance & Transparency Portal")
st.markdown("Track collections, view expenses, and access community bills and rules in one place.")

# Sidebar Navigation
menu = st.sidebar.selectbox("Navigation", ["Dashboard Summary", "Track Payments", "Log Expense & Bills", "Rules & Documents"])

# ----------------- 1. DASHBOARD SUMMARY -----------------
if menu == "Dashboard Summary":
    st.header("Financial Overview")
    
    try:
        # Fetch data
        pay_res = supabase.table("maintenance_payments").select("*").execute()
        exp_res = supabase.table("expenses").select("*").execute()
        
        df_pay = pd.DataFrame(pay_res.data) if pay_res.data else pd.DataFrame(columns=["amount", "status"])
        df_exp = pd.DataFrame(exp_res.data) if exp_res.data else pd.DataFrame(columns=["amount"])
        
        total_collected = df_pay[df_pay["status"] == "Paid"]["amount"].sum() if not df_pay.empty and "status" in df_pay.columns else 0
        total_expenses = df_exp["amount"].sum() if not df_exp.empty and "amount" in df_exp.columns else 0
        balance = total_collected - total_expenses
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Collections", f"₹ {total_collected:,.2f}")
        col2.metric("Total Expenses", f"₹ {total_expenses:,.2f}")
        col3.metric("Available Balance", f"₹ {balance:,.2f}")
        
        st.divider()
        st.subheader("Recent Expenses")
        if not df_exp.empty:
            st.dataframe(df_exp[["date", "category", "amount", "description"]], use_container_width=True)
        else:
            st.info("No expenses logged yet.")
            
    except Exception as e:
        st.error(f"Error loading dashboard data: {e}")

# ----------------- 2. TRACK PAYMENTS -----------------
elif menu == "Track Payments":
    st.header("Resident Maintenance Dues")
    
    # Committee action to add/update payment status
    with st.expander("Update / Add Resident Payment Status (Committee Only)"):
        with st.form("payment_form"):
            flat_no = st.text_input("Flat Number (e.g., Flat 201)")
            resident_name = st.text_input("Resident Name")
            month = st.selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])
            amount = st.number_input("Amount (₹)", value=2000.0)
            status = st.selectbox("Status", ["Paid", "Pending"])
            
            submitted = st.form_submit_button("Save Record")
            if submitted:
                supabase.table("maintenance_payments").insert({
                    "flat_no": flat_no,
                    "resident_name": resident_name,
                    "month": month,
                    "amount": amount,
                    "status": status
                }).execute()
                st.success("Payment status updated successfully!")
                st.rerun()

    # Display current records table
    res = supabase.table("maintenance_payments").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No payment records found.")

# ----------------- 3. LOG EXPENSE & BILLS -----------------
elif menu == "Log Expense & Bills":
    st.header("Log Association Expense & Upload Bills")
    
    with st.form("expense_form"):
        date = st.date_input("Expense Date")
        category = st.selectbox("Category", ["Electricity / Power", "Water Tanker", "Security Services", "Cleaning / Maintenance", "Repairs", "Other"])
        amount = st.number_input("Amount Spent (₹)")
        description = st.text_input("Description (e.g., June electricity bill)")
        uploaded_file = st.file_uploader("Upload Bill / Receipt Proof (PDF, PNG, JPG)")
        
        submitted = st.form_submit_button("Submit Expense")
        if submitted:
            receipt_url = ""
            if uploaded_file is not None:
                file_path = f"bills/{uploaded_file.name}"
                # Upload file to Supabase Storage bucket 'apartment-docs'
                supabase.storage.from_("apartment-docs").upload(file_path, uploaded_file.getvalue(), file_options={"upsert": "true"})
                receipt_url = supabase.storage.from_("apartment-docs").get_public_url(file_path)
            
            supabase.table("expenses").insert({
                "date": str(date),
                "category": category,
                "amount": amount,
                "description": description,
                "receipt_url": receipt_url
            }).execute()
            st.success("Expense logged and bill uploaded successfully!")

    st.divider()
    st.subheader("All Expenses & Proof Links")
    res = supabase.table("expenses").select("*").execute()
    if res.data:
        for item in res.data:
            cols = st.columns([2, 2, 2, 3, 2])
            cols[0].write(item.get("date"))
            cols[1].write(item.get("category"))
            cols[2].write(f"₹ {item.get('amount')}")
            cols[3].write(item.get("description"))
            if item.get("receipt_url"):
                cols[4].markdown(f"[View Bill Proof]({item.get('receipt_url')})", unsafe_allow_html=True)
            else:
                cols[4].write("No file attached")
    else:
        st.info("No expenses recorded.")

# ----------------- 4. RULES & DOCUMENTS -----------------
elif menu == "Rules & Documents":
    st.header("Apartment Bylaws, Rules & Circulars")
    
    # Upload general documents (like society rules)
    with st.expander("Upload General Document / Rulebook"):
        with st.form("rule_form"):
            doc_name = st.text_input("Document Title (e.g., Society Rules 2026)")
            rule_file = st.file_uploader("Upload PDF / Document")
            doc_submitted = st.form_submit_button("Upload Document")
            
            if doc_submitted and rule_file:
                file_path = f"rules/{rule_file.name}"
                supabase.storage.from_("apartment-docs").upload(file_path, rule_file.getvalue(), file_options={"upsert": "true"})
                file_url = supabase.storage.from_("apartment-docs").get_public_url(file_path)
                
                # Save metadata into a table or display directly
                st.success(f"Uploaded successfully! Public Link: {file_url}")

    st.markdown("### Available Association Documents")
    # List files from Supabase storage folder
    try:
        files = supabase.storage.from_("apartment-docs").list("rules")
        if files:
            for f in files:
                if f['name'] != '.emptyFolderPlaceholder':
                    file_url = supabase.storage.from_("apartment-docs").get_public_url(f"rules/{f['name']}")
                    st.markdown(f"- 📄 [{f['name']}ڧ]({file_url})")
        else:
            st.info("No rules or bylaws uploaded yet.")
    except Exception:
        st.info("Upload documents above to see them listed here.")