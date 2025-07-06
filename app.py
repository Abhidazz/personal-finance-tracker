import streamlit as st
import bcrypt
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from config import MONGO_URI, DB_NAME

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db["users"]
transactions_collection = db["transactions"]

# --- Auth Helpers ---
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def show_login_or_signup():
    st.title("🔐 Login / Sign Up")

    auth_mode = st.radio("Select Mode", ["Login", "Sign Up"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if auth_mode == "Sign Up":
        confirm_password = st.text_input("Confirm Password", type="password")
        if st.button("Create Account"):
            if password != confirm_password:
                st.error("❌ Passwords do not match!")
            elif users_collection.find_one({"username": username}):
                st.warning("⚠️ Username already exists.")
            else:
                hashed_pw = hash_password(password)
                users_collection.insert_one({"username": username, "password": hashed_pw})
                st.success("✅ Account created! Please login.")
    else:
        if st.button("Login"):
            user = users_collection.find_one({"username": username})
            if user and verify_password(password, user["password"]):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")

# --- Load User's Data from MongoDB ---
def load_user_data(username):
    data = list(transactions_collection.find({"username": username}))
    if not data:
        return pd.DataFrame(columns=["date", "amount", "category", "description"])
    
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["date"])
    df.set_index("date", inplace=True)
    return df

# --- Save Entry to MongoDB ---
def save_transaction(username, date, amount, category, description):
    transactions_collection.insert_one({
        "username": username,
        "date": date,
        "amount": amount,
        "category": category,
        "description": description
    })

# --- Dashboard ---
def show_dashboard():
    st.set_page_config(page_title="💸 Personal Finance Tracker", layout="centered")
    st.title("💸 Personal Finance Tracker")
    st.write(f"Welcome, {st.session_state.username}!")

    # Add Transaction
    st.header("➕ Add Transaction")
    with st.form("entry_form"):
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Category", options=["INCOME", "EXPENSE"])
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
        with col2:
            date = st.date_input("Date", value=datetime.today())
            description = st.text_input("Description")
        submitted = st.form_submit_button("Add")
        if submitted:
            save_transaction(
                username=st.session_state.username,
                date=date.strftime("%d-%m-%Y"),
                amount=amount,
                category=category,
                description=description
            )
            st.success("Transaction added successfully!")

    # Load Data
    df = load_user_data(st.session_state.username)
    st.header("📊 Transaction History & Summary")

    if df.empty:
        st.info("No transactions found.")
    else:
        keyword = st.text_input("🔍 Search in description (optional)")
        df["month"] = df.index.to_period("M")
        unique_months = df["month"].dt.strftime("%Y-%m").unique().tolist()
        selected_month = st.selectbox("Select Month", options=unique_months)
        df_filtered = df[df["month"].dt.strftime("%Y-%m") == selected_month]

        if keyword:
            df_filtered = df_filtered[df_filtered["description"].str.contains(keyword, case=False, na=False)]

        if df_filtered.empty:
            st.warning("No data in selected range or matching search.")
        else:
            with st.expander("View Filtered Transactions"):
                st.dataframe(df_filtered.sort_index(ascending=False))

            # Budget
            st.subheader("💰 Set Your Monthly Budget")
            budget = st.number_input("Monthly Budget (₹)", min_value=0.0, format="%.2f")

            # Summary
            st.subheader("📈 Summary")
            income = df_filtered[df_filtered["category"].str.upper() == "INCOME"]["amount"].sum()
            expense = df_filtered[df_filtered["category"].str.upper() == "EXPENSE"]["amount"].sum()
            net = income - expense

            st.metric("Total Income", f"₹ {income:,.2f}")
            st.metric("Total Expense", f"₹ {expense:,.2f}")
            st.metric("Net Saving", f"₹ {net:,.2f}")

            if budget > 0 and expense > budget:
                st.error(f"🚨 Budget exceeded by ₹{expense - budget:,.2f}!")

            # Line Chart
            st.subheader("📉 Income vs Expense Chart")
            daily = df_filtered.groupby([df_filtered.index.date, "category"])["amount"].sum().unstack().fillna(0)
            st.line_chart(daily)

            # Pie Chart
            st.subheader("📌 Category-wise Distribution")
            pie_data = df_filtered.groupby("category")["amount"].sum()
            fig, ax = plt.subplots()
            pie_data.plot.pie(autopct="%1.1f%%", ax=ax, ylabel="")
            st.pyplot(fig)

            # Download button
            st.download_button("📥 Download CSV", data=df_filtered.reset_index().to_csv(index=False),
                               file_name="filtered_finance_data.csv", mime="text/csv")

# --- App Entry ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    show_login_or_signup()
else:
    show_dashboard()