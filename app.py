import streamlit as st

def check_login():
    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None

    # If not logged in, show login form
    if not st.session_state["authenticated"]:
        st.sidebar.header("🔑 Login")
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        login_btn = st.sidebar.button("Login")

        if login_btn:
            users = st.secrets["users"]
            if username in users and password == users[username]:
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success(f"Login successful ✅ Welcome, {username}")
            else:
                st.error("Invalid username or password")

        if not st.session_state["authenticated"]:
            st.stop()  # Prevent rest of app from loading until login

    # If logged in, show logout option
    else:
        st.sidebar.write(f"👋 Logged in as **{st.session_state['username']}**")
        if st.sidebar.button("Logout"):
            st.session_state["authenticated"] = False
            st.session_state["username"] = None
            st.experimental_rerun()  # Restart app to show login form again

# Call login check before main app
check_login()

# --- Your finance app code continues below ---
st.title("💰 Personal Finance Tracker")


import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import date

st.set_page_config(page_title="Personal Finance Tracker", page_icon="💰", layout="wide")

# ---------- Persistence (optional CSV) ----------
CSV_FILE = "finance_data.csv"

def load_data():
    try:
        df = pd.read_csv(CSV_FILE, parse_dates=["Date"])
        return df
    except Exception:
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "Description"])

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# ---------- Initialize ----------
if "data" not in st.session_state:
    st.session_state["data"] = load_data()

st.title("💰 Personal Finance Tracker")

# ---------- Sidebar filters ----------
with st.sidebar:
    st.header("Filters")
    types = st.multiselect("Entry types", ["Income", "Expense", "Usage"], default=["Income", "Expense", "Usage"])
    categories_available = sorted(st.session_state["data"]["Category"].dropna().unique().tolist())
    categories = st.multiselect("Categories", categories_available, default=categories_available)
    start_date = st.date_input("Start date", value=min(st.session_state["data"]["Date"]).date() if not st.session_state["data"].empty else date.today())
    end_date = st.date_input("End date", value=max(st.session_state["data"]["Date"]).date() if not st.session_state["data"].empty else date.today())

# ---------- Add entry form ----------
st.subheader("➕ Add entry")
with st.form("entry_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        entry_type = st.selectbox("Type", ["Income", "Expense", "Usage"])
        category = st.text_input("Category", placeholder="e.g., Salary, Food, Electricity")
    with col2:
        amount = st.number_input("Amount", min_value=0.0, step=0.01, format="%.2f")
        entry_date = st.date_input("Date", value=date.today())
    with col3:
        description = st.text_input("Description", placeholder="Optional notes")

    submitted = st.form_submit_button("Add entry")
    if submitted:
        new_entry = {
            "Date": pd.to_datetime(entry_date),
            "Type": entry_type,
            "Category": category.strip() if category else None,
            "Amount": float(amount),
            "Description": description.strip() if description else None,
        }
        st.session_state["data"] = pd.concat([st.session_state["data"], pd.DataFrame([new_entry])], ignore_index=True)
        save_data(st.session_state["data"])
        st.success("Entry added")

# ---------- Filtered view ----------
df = st.session_state["data"].copy()

if not df.empty:
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    mask = (
        df["Type"].isin(types)
        & df["Date"].between(start_date, end_date)
        & (df["Category"].isin(categories) if categories else True)
    )
    filtered = df[mask].copy()
else:
    filtered = df

st.subheader("📊 Records")
st.dataframe(filtered, use_container_width=True)

# ---------- Summary ----------
st.subheader("📈 Summary")
if not filtered.empty:
    totals = filtered.groupby("Type")["Amount"].sum()
    income_total = float(totals.get("Income", 0.0))
    expense_total = float(totals.get("Expense", 0.0))
    usage_total = float(totals.get("Usage", 0.0))
    net = income_total - (expense_total + usage_total)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Income total", f"{income_total:,.2f}")
    c2.metric("Expense total", f"{expense_total:,.2f}")
    c3.metric("Usage total", f"{usage_total:,.2f}")
    c4.metric("Net", f"{net:,.2f}")

    # Monthly roll-up
    monthly = (
        pd.DataFrame(st.session_state["data"])
        .assign(Date=pd.to_datetime(st.session_state["data"]["Date"]))
        .set_index("Date")
        .groupby([pd.Grouper(freq="M"), "Type"])["Amount"]
        .sum()
        .unstack(fill_value=0)
        .sort_index()
    )

    st.caption("Monthly overview (from full dataset)")
    st.line_chart(monthly, use_container_width=True)
else:
    st.info("No records match your filters.")

# ---------- Charts ----------
st.subheader("📉 Breakdown")
colA, colB = st.columns(2)

with colA:
    exp = filtered[filtered["Type"] == "Expense"]
    if not exp.empty:
        fig, ax = plt.subplots(figsize=(4, 4))
        exp.groupby("Category")["Amount"].sum().plot(kind="pie", autopct="%1.1f%%", ax=ax)
        ax.set_ylabel("")
        ax.set_title("Expenses by category")
        st.pyplot(fig)
    else:
        st.info("No expenses to chart.")

with colB:
    use = filtered[filtered["Type"] == "Usage"]
    if not use.empty:
        fig, ax = plt.subplots(figsize=(4, 4))
        use.groupby("Category")["Amount"].sum().plot(kind="bar", ax=ax, color="#f39c12")
        ax.set_title("Usage by category")
        ax.set_xlabel("Category")
        ax.set_ylabel("Amount")
        st.pyplot(fig)
    else:
        st.info("No usage to chart.")

# ---------- Export ----------
def to_excel(df_export: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, index=False, sheet_name="FinanceData")
    return output.getvalue()

excel_bytes = to_excel(st.session_state["data"])
st.download_button(
    label="📥 Export all data to Excel",
    data=excel_bytes,
    file_name="personal_finance_data.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)


st.caption("Tip: Filters only affect the view and charts. The export includes the full dataset.")


