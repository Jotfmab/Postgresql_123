import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import datetime
import sqlalchemy

# ------------------------------------------------------------------------------
# Database Connection Setup
# ------------------------------------------------------------------------------
# In your Streamlit Cloud secrets.toml, include:
# [postgres]
# connection_string = "postgresql://username:password@hostname:port/databasename"

@st.cache_resource
def get_engine():
    connection_string = st.secrets["postgres"]["connection_string"]
    engine = sqlalchemy.create_engine(connection_string)
    return engine

# ------------------------------------------------------------------------------
# 1. LOAD TIMELINE DATA FROM POSTGRES
# ------------------------------------------------------------------------------
# (Temporarily removed caching to ensure fresh data is loaded.)
def load_timeline_data() -> pd.DataFrame:
    engine = get_engine()
    query = 'SELECT * FROM "Contrcution_Timeline"'
    df = pd.read_sql(query, engine)
    df.columns = df.columns.str.strip()
    mapping = {
        "activity": "Activity",
        "item": "Item",
        "task": "Task",
        "room": "Room",
        "location": "Location",
        "notes": "Notes",
        "start_date": "Start Date",
        "end_date": "End Date",
        "status": "Status",
        "workdays": "Workdays",
        "progress": "Progress"
    }
    df.rename(columns=mapping, inplace=True)
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    if "End Date" in df.columns:
        df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    df["Status"] = df["Status"].astype(str).fillna("Not Started")
    return df

# ------------------------------------------------------------------------------
# 2. LOAD ITEMS DATA FROM POSTGRES
# ------------------------------------------------------------------------------
def load_items_data() -> pd.DataFrame:
    engine = get_engine()
    query = 'SELECT * FROM "Items_Order"'
    df = pd.read_sql(query, engine)
    df.columns = df.columns.str.strip()
    mapping = {
        "item": "Item",
        "quantity": "Quantity",
        "order_status": "Order Status",
        "delivery_status": "Delivery Status",
        "notes": "Notes"
    }
    df.rename(columns=mapping, inplace=True)
    df["Item"] = df["Item"].astype(str)
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
    df["Order Status"] = df["Order Status"].astype(str)
    df["Delivery Status"] = df["Delivery Status"].astype(str)
    df["Notes"] = df["Notes"].astype(str)
    return df

# ------------------------------------------------------------------------------
# 3. SAVE FUNCTIONS (Write back to Postgres)
# ------------------------------------------------------------------------------
def save_timeline_data(df: pd.DataFrame):
    engine = get_engine()
    with engine.begin() as conn:
        df.to_sql("Contrcution_Timeline", conn, if_exists="replace", index=False)
    # Optionally, force a rerun to reload fresh data:
    st.success("Timeline data successfully saved!")
    st.experimental_rerun()

def save_items_data(df: pd.DataFrame):
    engine = get_engine()
    with engine.begin() as conn:
        df.to_sql("Items_Order", conn, if_exists="replace", index=False)
    st.success("Items table successfully saved!")
    st.experimental_rerun()

# ------------------------------------------------------------------------------
# APP CONFIGURATION & TITLE
# ------------------------------------------------------------------------------
st.set_page_config(page_title="Construction Project Manager Dashboard", layout="wide")
st.title("Construction Project Manager Dashboard")
st.markdown(
    "This dashboard provides an overview of the construction project, including task snapshots, "
    "timeline visualization, and progress tracking. Use the sidebar to filter and update data."
)

# Add a Refresh Data button to force a new load from the database.
if st.button("Refresh Data"):
    st.experimental_rerun()

# ------------------------------------------------------------------------------
# 4. MAIN TIMELINE: DATA EDITOR & ROW/COLUMN MANAGEMENT
# ------------------------------------------------------------------------------
df_main = load_timeline_data()

st.subheader("Update Task Information (Main Timeline)")

with st.sidebar.expander("Row & Column Management (Main Timeline)"):
    st.markdown("*Delete a row by index*")
    delete_index = st.text_input("Enter row index to delete (main table)", value="")
    if st.button("Delete Row (Main)"):
        if delete_index.isdigit():
            idx = int(delete_index)
            if 0 <= idx < len(df_main):
                df_main.drop(df_main.index[idx], inplace=True)
                try:
                    save_timeline_data(df_main)
                except Exception as e:
                    st.sidebar.error(f"Error saving data: {e}")
            else:
                st.sidebar.error("Invalid index.")
        else:
            st.sidebar.error("Please enter a valid integer index.")

    st.markdown("*Add a new column*")
    new_col_name = st.text_input("New Column Name (main table)", value="")
    new_col_type = st.selectbox("Column Type (main table)", ["string", "integer", "float", "datetime"])
    if st.button("Add Column (Main)"):
        if new_col_name and new_col_name not in df_main.columns:
            if new_col_type == "string":
                df_main[new_col_name] = ""
                df_main[new_col_name] = df_main[new_col_name].astype(object)
            elif new_col_type == "integer":
                df_main[new_col_name] = 0
            elif new_col_type == "float":
                df_main[new_col_name] = 0.0
            elif new_col_type == "datetime":
                df_main[new_col_name] = pd.NaT
            try:
                save_timeline_data(df_main)
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        else:
            st.sidebar.warning("Column already exists or invalid name.")

    st.markdown("*Delete a column*")
    col_to_delete = st.selectbox(
        "Select Column to Delete (main table)",
        options=[""] + list(df_main.columns),
        index=0
    )
    if st.button("Delete Column (Main)"):
        if col_to_delete and col_to_delete in df_main.columns:
            df_main.drop(columns=[col_to_delete], inplace=True)
            try:
                save_timeline_data(df_main)
            except Exception as e:
                st.sidebar.error(f"Error saving data: {e}")
        else:
            st.sidebar.warning("Please select a valid column.")

# Configure columns for the data editor.
column_config_main = {}
for col in ["Activity", "Item", "Task", "Room", "Location"]:
    if col in df_main.columns:
        column_config_main[col] = st.column_config.TextColumn(
            col,
            help=f"Enter or select a value for {col}."
        )
if "Status" in df_main.columns:
    column_config_main["Status"] = st.column_config.SelectboxColumn(
        "Status", options=["Finished", "In Progress", "Not Started", "Delayed"], help="Status"
    )
if "Progress" in df_main.columns:
    column_config_main["Progress"] = st.column_config.NumberColumn(
        "Progress", min_value=0, max_value=100, step=1, help="Progress %"
    )
if "Start Date" in df_main.columns:
    column_config_main["Start Date"] = st.column_config.DateColumn(
        "Start Date", help="Project start date"
    )
if "End Date" in df_main.columns:
    column_config_main["End Date"] = st.column_config.DateColumn(
        "End Date", help="Project end date"
    )

edited_df_main = st.data_editor(
    df_main,
    column_config=column_config_main,
    use_container_width=True,
    num_rows="dynamic",
    key="timeline_data_editor"
)

if "Status" in edited_df_main.columns:
    edited_df_main["Status"] = edited_df_main["Status"].astype(str).fillna("Not Started")

if st.button("Save Updates (Main Timeline)"):
    edited_df_main.loc[edited_df_main["Status"].str.lower() == "finished", "Progress"] = 100
    try:
        save_timeline_data(edited_df_main)
    except Exception as e:
        st.error(f"Error saving main timeline: {e}")

# ... (Rest of your code remains unchanged for filters, Gantt chart, KPIs, and Items table)

# ------------------------------------------------------------------------------
# 9. SECOND TABLE: ITEMS TO ORDER
# ------------------------------------------------------------------------------
st.header("Items to Order")
df_items = load_items_data()
for needed_col in ["Item", "Quantity", "Order Status", "Delivery Status", "Notes"]:
    if needed_col not in df_items.columns:
        df_items[needed_col] = ""
df_items["Item"] = df_items["Item"].astype(str)
df_items["Quantity"] = pd.to_numeric(df_items["Quantity"], errors="coerce").fillna(0).astype(int)
df_items["Order Status"] = df_items["Order Status"].astype(str)
df_items["Delivery Status"] = df_items["Delivery Status"].astype(str)
df_items["Notes"] = df_items["Notes"].astype(str)

items_col_config = {
    "Item": st.column_config.TextColumn("Item", help="Enter the name of the item."),
    "Quantity": st.column_config.NumberColumn("Quantity", min_value=0, step=1, help="Enter the quantity required."),
    "Order Status": st.column_config.SelectboxColumn("Order Status", options=["Ordered", "Not Ordered"], help="Choose if this item is ordered or not."),
    "Delivery Status": st.column_config.SelectboxColumn("Delivery Status", options=["Delivered", "Not Delivered", "Delayed"], help="Delivery status of the item."),
    "Notes": st.column_config.TextColumn("Notes", help="Enter any notes or remarks here.")
}

edited_df_items = st.data_editor(
    df_items,
    column_config=items_col_config,
    use_container_width=True,
    num_rows="dynamic",
    key="items_data_editor"
)

if st.button("Save Items Table"):
    try:
        edited_df_items["Quantity"] = pd.to_numeric(edited_df_items["Quantity"], errors="coerce").fillna(0).astype(int)
        save_items_data(edited_df_items)
    except Exception as e:
        st.error(f"Error saving items table: {e}")

csv_buffer = io.StringIO()
edited_df_items.to_csv(csv_buffer, index=False)
st.download_button(
    label="Download Items Table as CSV",
    data=csv_buffer.getvalue(),
    file_name="Cleaned_Items_Table.csv",
    mime="text/csv"
)
