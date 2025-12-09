import streamlit as st
import pandas as pd
from datetime import date
from streamlit_cookies_manager import EncryptedCookieManager
import io

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
tab1, tab2, tab3 = st.tabs([
    "📊 Dashboard / Summary",
    "📥 Entry / Transaction",
    "⚙️ Config"
])

# ---------------- DASHBOARD -----------------
with tab1:
    st.header("📊 Dashboard / Summary")
    df = st.session_state["data"]

    if not df.empty:
        summary = df.groupby("Type")["Amount"].sum()
        st.metric("Total Income", f"{summary.get('Income',0):,.2f}")
        st.metric("Total Usage", f"{summary.get('Usage',0):,.2f}")
        st.metric("Net", f"{summary.get('Income',0)-summary.get('Usage',0):,.2f}")

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
 
# ---------------- ENTRY PAGE ----------------
with tab2:
    st.header("➕ Add transaction")
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
            st.rerun()

    st.header("📋 Transaction table")
    df = st.session_state["data"]

    if not df.empty:
        # Show a beautified, editable table
        # Note: st.data_editor returns the edited DataFrame; we persist if changed.
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Date": st.column_config.DateColumn("Date"),
                "Type": st.column_config.SelectboxColumn("Type", options=["Income","Usage"]),
                "Category": st.column_config.TextColumn("Category"),
                "Item": st.column_config.TextColumn("Item"),
                "Amount": st.column_config.NumberColumn("Amount", step=0.01, help="Amount in your currency"),
                "Description": st.column_config.TextColumn("Description"),
            },
            key="transaction_editor",
        )

        # If any cell changed, save the edited table
        if not edited_df.equals(df):
            # Ensure Date column is datetime
            if "Date" in edited_df.columns:
                edited_df["Date"] = pd.to_datetime(edited_df["Date"])
            st.session_state["data"] = edited_df.reset_index(drop=True)
            st.success("Table changes saved ✅")

        st.divider()
        st.subheader("📤 Export / Import")

        # Export to Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            st.session_state["data"].to_excel(writer, index=False, sheet_name="Transactions")
        excel_data = output.getvalue()
        st.download_button(
            label="⬇️ Download as Excel",
            data=excel_data,
            file_name="transactions.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Import from CSV
        st.subheader("📥 Import Transactions (CSV)")
        uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"], key="import_csv")

            if uploaded_file is not None:
                if st.button("Import Transactions"):
                    try:
                        new_df = pd.read_csv(uploaded_file)
                        required_cols = ["Date","Type","Category","Item","Amount","Description"]
                        if all(col in new_df.columns for col in required_cols):
                            new_df["Date"] = pd.to_datetime(new_df["Date"], errors="coerce")
                            st.session_state["data"] = pd.concat([st.session_state["data"], new_df], ignore_index=True)
                            st.success("Transactions imported ✅")
                            # Clear the uploader after import
                            st.session_state["import_csv"] = None
                            st.rerun()
                        else:
                            st.error(f"CSV must contain columns: {', '.join(required_cols)}")
                    except Exception as e:
                        st.error(f"Error reading CSV: {e}")

 

        st.divider()
        st.subheader("🔧 Row actions")
        st.caption("Use icons to edit a single row with dropdowns, or delete it.")

        # Action icons per row (edit/delete)
        for i in range(len(st.session_state["data"])):
            row = st.session_state["data"].iloc[i]
            cols = st.columns([7,1,1])
            with cols[0]:
                st.write(f"[{i}] {row['Date'].date()} • {row['Type']} • {row['Category']} • {row['Item']} • {row['Amount']:.2f}")
            with cols[1]:
                if st.button("✏️", key=f"edit_icon_{i}"):
                    st.session_state["edit_row_index"] = i
            with cols[2]:
                if st.button("🗑️", key=f"delete_icon_{i}"):
                    st.session_state["data"] = st.session_state["data"].drop(st.session_state["data"].index[i]).reset_index(drop=True)
                    st.success(f"Deleted row {i} ✅")
                    st.rerun()

        # Inline row editor (with dropdowns) triggered by the edit icon
        if st.session_state["edit_row_index"] is not None:
            idx = st.session_state["edit_row_index"]
            row = st.session_state["data"].iloc[idx]
            st.divider()
            st.subheader(f"✏️ Edit transaction (row {idx})")

            with st.form("inline_row_edit"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_type = st.selectbox("Type", ["Income","Usage"], index=["Income","Usage"].index(row["Type"]))
                    # Dropdown if exists, otherwise text box
                    if st.session_state["categories"] and row["Category"] in st.session_state["categories"]:
                        new_category = st.selectbox("Category", st.session_state["categories"],
                                                    index=st.session_state["categories"].index(row["Category"]))
                    else:
                        new_category = st.text_input("Category", value=row["Category"])
                with c2:
                    if st.session_state["items"] and row["Item"] in st.session_state["items"]:
                        new_item = st.selectbox("Item", st.session_state["items"],
                                                index=st.session_state["items"].index(row["Item"]))
                    else:
                        new_item = st.text_input("Item", value=row["Item"])
                    new_amount = st.number_input("Amount", value=float(row["Amount"]), min_value=0.0, step=0.01)
                with c3:
                    new_date = st.date_input("Date", value=pd.to_datetime(row["Date"]).date())
                    new_description = st.text_input("Description", value=str(row["Description"]))

                save = st.form_submit_button("Save changes")
                cancel = st.form_submit_button("Cancel")

                if save:
                    st.session_state["data"].at[idx, "Date"] = pd.to_datetime(new_date)
                    st.session_state["data"].at[idx, "Type"] = new_type
                    st.session_state["data"].at[idx, "Category"] = new_category.strip()
                    st.session_state["data"].at[idx, "Item"] = new_item.strip()
                    st.session_state["data"].at[idx, "Amount"] = float(new_amount)
                    st.session_state["data"].at[idx, "Description"] = new_description.strip()
                    st.session_state["edit_row_index"] = None
                    st.success(f"Row {idx} updated ✅")
                    st.rerun()

                if cancel:
                    st.session_state["edit_row_index"] = None
                    st.info("Edit cancelled")
                    st.rerun()
    else:
        st.info("No transactions yet.")


  

# ---------------- CONFIG PAGE ----------------
with tab3:
    st.header("📂 Category Manager")
    with st.form("category_form", clear_on_submit=True):
        new_category = st.text_input("Add new category")
        add_cat = st.form_submit_button("Add Category")
        if add_cat and new_category.strip():
            st.session_state["categories"].append(new_category.strip())
            st.success(f"Category '{new_category.strip()}' added ✅")

    if st.session_state["categories"]:
        for i, cat in enumerate(st.session_state["categories"]):
            col1, col2, col3 = st.columns([4,1,1])
            col1.write(f"- {cat}")
            if col2.button("✏️", key=f"edit_cat_{i}"):
                new_name = st.text_input("Rename category", value=cat, key=f"rename_cat_{i}")
                if st.button("Save", key=f"save_cat_{i}"):
                    st.session_state["categories"][i] = new_name.strip()
                    st.rerun()
            if col3.button("❌", key=f"del_cat_{i}"):
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
        for i, itm in enumerate(st.session_state["items"]):
            col1, col2, col3 = st.columns([4,1,1])
            col1.write(f"- {itm}")
            if col2.button("✏️", key=f"edit_item_{i}"):
                new_name = st.text_input("Rename item", value=itm, key=f"rename_item_{i}")
                if st.button("Save", key=f"save_item_{i}"):
                    st.session_state["items"][i] = new_name.strip()
                    st.rerun()
            if col3.button("❌", key=f"del_item_{i}"):
                st.session_state["items"].pop(i)
                st.rerun()
    else:
        st.info("No items defined yet.")

    st.header("💰 Budget Setup")
    with st.form("budget_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            budget_category = st.selectbox("Category", st.session_state["categories"])
            #budget_category = st.text_input("Category")
        with col2:
            budget_item = st.selectbox("Item", st.session_state["items"]) if st.session_state["items"] else st.text_input("Item")
            #budget_item = st.text_input("Item")
        with col3:
            budget_amount = st.number_input("Budget amount", min_value=0.0, step=0.01)

        budget_submit = st.form_submit_button("Save Budget")
        if budget_submit:
            new_budget = {"Category":budget_category.strip(),"Item":budget_item.strip(),"Budget":float(budget_amount)}
            st.session_state["budgets"] = pd.concat([st.session_state["budgets"], pd.DataFrame([new_budget])], ignore_index=True)
            st.success("Budget saved ✅")

    if not st.session_state["budgets"].empty:
        st.dataframe(st.session_state["budgets"].reset_index(drop=True), use_container_width=True)

    






















