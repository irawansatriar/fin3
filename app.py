import streamlit as st
import pandas as pd
from datetime import date
from streamlit_cookies_manager import EncryptedCookieManager

# ---------------- COOKIE MANAGER ----------------
cookies = EncryptedCookieManager(
    prefix="finance_app", 
    password="Bi@sanyseperti"   # change this to a strong secret
)
if not cookies.ready():
    st.stop()

# ---------------- LOGIN CHECK ----------------
def check_login():
    # Restore from cookie
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = cookies.get("authenticated") == "true"
    if "username" not in st.session_state:
        st.session_state["username"] = cookies.get("username")

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
                cookies["authenticated"] = "true"
                cookies["username"] = username
                cookies.save()
                st.success(f"Login successful ✅ Welcome, {username}")
                st.rerun()
            else:
                st.error("Invalid username or password")

        if not st.session_state["authenticated"]:
            st.stop()
    else:
        st.sidebar.write(f"👋 Logged in as **{st.session_state['username']}**")
        if st.sidebar.button("Logout"):
            st.session_state["authenticated"] = False
            st.session_state["username"] = None
            cookies["authenticated"] = "false"
            cookies["username"] = ""
            cookies.save()
            st.rerun()

check_login()

# ---------------- INITIALIZE DATA ----------------
if "data" not in st.session_state:
    st.session_state["data"] = pd.DataFrame(columns=["Date","Type","Category","Item","Amount","Description"])
if "budgets" not in st.session_state:
    st.session_state["budgets"] = pd.DataFrame(columns=["Category","Item","Budget"])
if "categories" not in st.session_state:
    st.session_state["categories"] = []
if "items" not in st.session_state:
    st.session_state["items"] = []

# ---------------- TABS ----------------
tab1, tab2 = st.tabs(["📥 Entry Page", "⚙️ Config Page"])

# ---------------- ENTRY PAGE ----------------
with tab1:
    st.header("➕ Add Income / Usage Entry")
    with st.form("entry_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_type = st.selectbox("Type", ["Income", "Usage"])
            category = st.selectbox("Category", st.session_state["categories"]) if st.session_state["categories"] else st.text_input("Category")
        with col2:
            item = st.selectbox("Item", st.session_state["items"]) if st.session_state["items"] else st.text_input("Item")
            amount = st.number_input("Amount", min_value=0.0, step=0.01)
        with col3:
            entry_date = st.date_input("Date", value=date.today())
            description = st.text_input("Description")

        submitted = st.form_submit_button("Add Entry")
        if submitted:
            new_entry = {
                "Date": pd.to_datetime(entry_date),
                "Type": entry_type,
                "Category": category.strip(),
                "Item": item.strip(),
                "Amount": float(amount),
                "Description": description.strip(),
            }
            st.session_state["data"] = pd.concat([st.session_state["data"], pd.DataFrame([new_entry])], ignore_index=True)
            st.success("Entry added ✅")

    st.header("📊 Dashboard / Summary / Analysis")
    df = st.session_state["data"]
    if not df.empty:
        st.dataframe(df.reset_index(drop=True), use_container_width=True)

        # --- Delete Entry ---
        st.subheader("🗑️ Delete Entry")
        delete_index = st.number_input("Row index to delete", min_value=0, max_value=len(df)-1, step=1)
        if st.button("Delete Selected Entry"):
            st.session_state["data"].drop(delete_index, inplace=True)
            st.session_state["data"].reset_index(drop=True, inplace=True)
            st.success("Entry deleted ✅")

        # --- Modify Entry ---
        st.subheader("✏️ Modify Entry")
        edit_index = st.number_input("Row index to edit", min_value=0, max_value=len(df)-1, step=1, key="edit_index")
        if st.button("Load Entry for Edit"):
            row = df.iloc[edit_index]
            with st.form("edit_form"):
                new_type = st.selectbox("Type", ["Income","Usage"], index=["Income","Usage"].index(row["Type"]))
                new_category = st.selectbox("Category", st.session_state["categories"]) if st.session_state["categories"] else st.text_input("Category", value=row["Category"])
                new_item = st.text_input("Item", value=row["Item"])
                new_amount = st.number_input("Amount", value=row["Amount"], min_value=0.0, step=0.01)
                new_date = st.date_input("Date", value=row["Date"].date())
                new_description = st.text_input("Description", value=row["Description"])
                save_edit = st.form_submit_button("Save Changes")
                if save_edit:
                    st.session_state["data"].iloc[edit_index] = [
                        pd.to_datetime(new_date),
                        new_type,
                        new_category.strip(),
                        new_item.strip(),
                        float(new_amount),
                        new_description.strip()
                    ]
                    st.success("Entry updated ✅")

        # Summary
        summary = df.groupby("Type")["Amount"].sum()
        st.metric("Total Income", f"{summary.get('Income',0):,.2f}")
        st.metric("Total Usage", f"{summary.get('Usage',0):,.2f}")
        st.metric("Net", f"{summary.get('Income',0)-summary.get('Usage',0):,.2f}")

        # Budget vs Usage
        st.subheader("Budget vs Usage")
        if not st.session_state["budgets"].empty:
            usage_summary = df[df["Type"]=="Usage"].groupby(["Category","Item"])["Amount"].sum().reset_index()
            merged = pd.merge(st.session_state["budgets"], usage_summary, on=["Category","Item"], how="left").fillna({"Amount":0})
            merged.rename(columns={"Amount":"Usage"}, inplace=True)
            merged["Remaining"] = merged["Budget"] - merged["Usage"]
            merged["Progress"] = merged["Usage"]/merged["Budget"]

            for _, row in merged.iterrows():
                st.write(f"**{row['Category']} - {row['Item']}**")
                st.progress(min(row["Progress"],1.0))
                st.caption(f"Used: {row['Usage']:.2f} / Budget: {row['Budget']:.2f} → Remaining: {row['Remaining']:.2f}")
        else:
            st.info("No budgets defined yet.")
    else:
        st.info("No entries yet.")

# ---------------- CONFIG PAGE ----------------
with tab2:
    st.header("📂 Category Manager")
    with st.form("category_form", clear_on_submit=True):
        new_category = st.text_input("Add new category")
        add_cat = st.form_submit_button("Add Category")
        if add_cat and new_category.strip():
            st.session_state["categories"].append(new_category.strip())
            st.success(f"Category '{new_category.strip()}' added ✅")

    if st.session_state["categories"]:
        st.subheader("🧾 Existing Categories")
        for i, cat in enumerate(st.session_state["categories"]):
            col1, col2 = st.columns([4, 1])
            col1.write(f"- {cat}")
            if col2.button("❌", key=f"del_cat_{i}"):
                st.session_state["categories"].pop(i)
                st.rerun()
    else:
        st.info("No categories defined yet.")

    st.header("📦 Item Manager")
    with st.form("item_form", clear_on_submit=True):
    new_item = st.text_input("Add new item")
    add_item = st.form_submit_button("Add Item")
    if add_item and new_item.strip():
        st.session_state["items"].append(new_item.strip())
        st.success(f"Item '{new_item.strip()}' added ✅")

if st.session_state["items"]:
    st.subheader("🧾 Existing Items")
    for i, itm in enumerate(st.session_state["items"]):
        col1, col2 = st.columns([4, 1])
        col1.write(f"- {itm}")
        if col2.button("❌", key=f"del_item_{i}"):
            st.session_state["items"].pop(i)
            st.rerun()
else:
    st.info("No items defined yet.")
    

