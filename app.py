import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import date, datetime, timedelta
from io import BytesIO

# ============================================================
# PAGE CONFIG & THEME
# ============================================================
st.set_page_config(
    page_title="HR Attendance, OT & Salary Portal",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_FILE = "attendance.db"

# ============================================================
# SECURITY & HASHING HELPERS
# ============================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# ============================================================
# DATABASE CONNECTION
# ============================================================
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def create_database():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS punching_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_date TEXT NOT NULL,
            punch_time TEXT NOT NULL,
            department TEXT,
            employee_code TEXT NOT NULL,
            employee_name TEXT,
            location_name TEXT,
            entry_exit TEXT,
            UNIQUE(transaction_date, punch_time, employee_code, location_name, entry_exit)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salary_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT UNIQUE NOT NULL,
            monthly_salary REAL DEFAULT 0,
            working_days REAL DEFAULT 26,
            daily_wage REAL DEFAULT 0,
            ot_rate REAL DEFAULT 0,
            attendance_allowance REAL DEFAULT 0,
            food_allowance REAL DEFAULT 0,
            travel_allowance REAL DEFAULT 0,
            other_allowance REAL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employee_salary (
            employee_code TEXT PRIMARY KEY,
            employee_name TEXT,
            category TEXT,
            extra_wages REAL DEFAULT 0,
            extra_allowance REAL DEFAULT 0,
            deduction REAL DEFAULT 0,
            remarks TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT
        )
    """)
    conn.commit()
    conn.close()

def seed_default_users_and_categories():
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM salary_categories")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO salary_categories
            (category, monthly_salary, working_days, daily_wage, ot_rate,
             attendance_allowance, food_allowance, travel_allowance, other_allowance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("General", 15000, 26, 576.92, 75, 50, 40, 50, 0))

    default_users = [
        ("admin", hash_password("admin123"), "Admin", "System Administrator"),
        ("hr", hash_password("hr123"), "HR", "HR Manager"),
        ("accounts", hash_password("acc123"), "Accounts", "Accounts Officer"),
        ("supervisor", hash_password("sup123"), "Supervisor", "Floor Supervisor"),
        ("employee", hash_password("emp123"), "Employee", "Test Employee")
    ]
    for uname, phash, role, fname in default_users:
        cur.execute("""
            INSERT OR IGNORE INTO users (username, password_hash, role, full_name)
            VALUES (?, ?, ?, ?)
        """, (uname, phash, role, fname))
    
    conn.commit()
    conn.close()

create_database()
seed_default_users_and_categories()

# ============================================================
# DATA LOADERS
# ============================================================
@st.cache_data
def load_data():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT id, transaction_date, punch_time, department, employee_code,
               employee_name, location_name, entry_exit
        FROM punching_data
        ORDER BY transaction_date DESC, punch_time DESC
    """, conn)
    conn.close()
    if not df.empty:
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        df["punch_time"] = df["punch_time"].astype(str)
    return df

@st.cache_data
def load_categories():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM salary_categories ORDER BY category", conn)
    conn.close()
    return df

@st.cache_data
def load_employee_salary():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM employee_salary ORDER BY employee_code", conn)
    conn.close()
    return df

@st.cache_data
def load_users():
    conn = get_connection()
    df = pd.read_sql_query("SELECT username, role, full_name FROM users ORDER BY username", conn)
    conn.close()
    return df

# ============================================================
# WRITE & MUTATION HELPERS
# ============================================================
def insert_punching_data(data):
    """Bulk insert normalized punch rows; existing duplicate handling is preserved."""
    if data.empty:
        return 0, 0
    cols = ["Transaction Date", "Time", "Department", "Employee Code", "Employee Name", "Location Name", "ENTRY/EXIT"]
    sql = """INSERT OR IGNORE INTO punching_data
        (transaction_date, punch_time, department, employee_code, employee_name, location_name, entry_exit)
        VALUES (?, ?, ?, ?, ?, ?, ?)"""
    conn = get_connection()
    inserted = 0
    try:
        cur = conn.cursor()
        rows = data[cols].itertuples(index=False, name=None)
        while True:
            batch = []
            try:
                for _ in range(5000):
                    batch.append(tuple(str(v) for v in next(rows)))
            except StopIteration:
                pass
            if not batch:
                break
            before = conn.total_changes
            cur.executemany(sql, batch)
            inserted += conn.total_changes - before
        conn.commit()
    finally:
        conn.close()
    duplicates = len(data) - inserted
    load_data.clear()
    return inserted, duplicates

def clear_punching_data():
    conn = get_connection()
    conn.execute("DELETE FROM punching_data")
    conn.commit()
    conn.close()
    st.cache_data.clear()

def save_category(row):
    conn = get_connection()
    conn.execute("""
        INSERT INTO salary_categories
        (category, monthly_salary, working_days, daily_wage, ot_rate,
         attendance_allowance, food_allowance, travel_allowance, other_allowance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(category) DO UPDATE SET
            monthly_salary=excluded.monthly_salary,
            working_days=excluded.working_days,
            daily_wage=excluded.daily_wage,
            ot_rate=excluded.ot_rate,
            attendance_allowance=excluded.attendance_allowance,
            food_allowance=excluded.food_allowance,
            travel_allowance=excluded.travel_allowance,
            other_allowance=excluded.other_allowance
    """, row)
    conn.commit()
    conn.close()
    st.cache_data.clear()

def delete_category(category):
    conn = get_connection()
    conn.execute("DELETE FROM salary_categories WHERE category=?", (category,))
    conn.commit()
    conn.close()
    st.cache_data.clear()

def save_employee_salary(row):
    conn = get_connection()
    conn.execute("""
        INSERT INTO employee_salary
        (employee_code, employee_name, category, extra_wages, extra_allowance, deduction, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(employee_code) DO UPDATE SET
            employee_name=excluded.employee_name,
            category=excluded.category,
            extra_wages=excluded.extra_wages,
            extra_allowance=excluded.extra_allowance,
            deduction=excluded.deduction,
            remarks=excluded.remarks
    """, row)
    conn.commit()
    conn.close()
    st.cache_data.clear()

def save_user(username, password, role, full_name):
    conn = get_connection()
    phash = hash_password(password)
    conn.execute("""
        INSERT INTO users (username, password_hash, role, full_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            password_hash=excluded.password_hash,
            role=excluded.role,
            full_name=excluded.full_name
    """, (username, phash, role, full_name))
    conn.commit()
    conn.close()
    st.cache_data.clear()

# ============================================================
# TIME & CALCULATION HELPERS
# ============================================================
def normalize_direction(value):
    v = str(value).strip().lower()
    if v in {"entry", "in", "checkin", "check-in", "punch in"}:
        return "IN"
    if v in {"exit", "out", "checkout", "check-out", "punch out"}:
        return "OUT"
    return v.upper()

def parse_time(value):
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.time()
    if hasattr(value, "time") and not isinstance(value, str):
        try:
            return value.time()
        except Exception:
            pass
    if isinstance(value, (int, float)):
        seconds = int(round(float(value) * 24 * 3600)) % 86400
        return (datetime.min + timedelta(seconds=seconds)).time()
    s = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).time()
    except Exception:
        return None

def format_td(td):
    if pd.isna(td) or td is None:
        return ""
    total = max(0, int(td.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def hours_float(td):
    if td is None or pd.isna(td):
        return 0.0
    return max(0.0, td.total_seconds() / 3600)

def normalize_punching(raw):
    data = raw.copy()
    mapping = {}
    for c in data.columns:
        key = str(c).strip().lower().replace("\n", " ")
        if key == "transaction date": mapping[c] = "Transaction Date"
        elif key == "time": mapping[c] = "Time"
        elif key == "department": mapping[c] = "Department"
        elif key == "employee code": mapping[c] = "Employee Code"
        elif key == "employee name": mapping[c] = "Employee Name"
        elif key == "location name": mapping[c] = "Location Name"
        elif "entry/exit" in key or ("entry" in key and "exit" in key) or key in {"in/out", "in out"}:
            mapping[c] = "ENTRY/EXIT"
    data = data.rename(columns=mapping)
    required = ["Transaction Date", "Time", "Employee Code", "Employee Name", "ENTRY/EXIT"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    for c in ["Department", "Location Name"]:
        if c not in data.columns:
            data[c] = ""
    data["Transaction Date"] = pd.to_datetime(data["Transaction Date"], errors="coerce").dt.date
    data["Time Parsed"] = data["Time"].apply(parse_time)
    data["ENTRY/EXIT"] = data["ENTRY/EXIT"].apply(normalize_direction)
    data["Employee Code"] = data["Employee Code"].astype(str).str.strip()
    data["Employee Name"] = data["Employee Name"].fillna("").astype(str).str.strip()
    data = data.dropna(subset=["Transaction Date", "Time Parsed", "Employee Code"])
    return data

def build_daily_report(punches, duty_hours=8):
    if punches.empty:
        return pd.DataFrame()
    x = punches.copy()
    x["Date"] = pd.to_datetime(x["Transaction Date"])
    x["Time"] = x["Time Parsed"].apply(lambda t: datetime.combine(date.today(), t) if t else pd.NaT)
    rows = []
    for (code, dt), g in x.groupby(["Employee Code", "Date"]):
        g = g.sort_values("Time")
        ins = g.loc[g["ENTRY/EXIT"] == "IN", "Time"]
        outs = g.loc[g["ENTRY/EXIT"] == "OUT", "Time"]
        first_in = ins.min() if not ins.empty else pd.NaT
        last_out = outs.max() if not outs.empty else pd.NaT
        work = (last_out - first_in) if pd.notna(first_in) and pd.notna(last_out) else pd.NaT
        duty = timedelta(hours=float(duty_hours))
        ot = max(work - duty, timedelta(0)) if pd.notna(work) else timedelta(0)
        short = max(duty - work, timedelta(0)) if pd.notna(work) else timedelta(0)
        rows.append({
            "Employee Code": str(code),
            "Employee Name": g["Employee Name"].iloc[0],
            "Department": g["Department"].iloc[0],
            "Location": g["Location Name"].iloc[0],
            "Date": dt.date(),
            "First IN": first_in.time() if pd.notna(first_in) else None,
            "Last OUT": last_out.time() if pd.notna(last_out) else None,
            "Working Hours": work,
            "Duty Hours": duty,
            "OT Hours": ot,
            "Short Hours": short,
            "IN Punches": int((g["ENTRY/EXIT"] == "IN").sum()),
            "OUT Punches": int((g["ENTRY/EXIT"] == "OUT").sum()),
            "Status": "Present" if pd.notna(first_in) else "Absent/No IN",
        })
    out = pd.DataFrame(rows)
    for c in ["Working Hours", "Duty Hours", "OT Hours", "Short Hours"]:
        if c in out.columns:
            out[c] = out[c].apply(format_td)
    return out.sort_values(["Date", "Employee Code"])

def build_salary_report(daily, categories, employee_master):
    if daily.empty:
        return pd.DataFrame()
    d = daily.copy()
    d["Date"] = pd.to_datetime(d["Date"])
    d["OT Hours Decimal"] = d["OT Hours"].apply(lambda x: hours_float(pd.to_timedelta(x)))
    attendance = d.groupby(["Employee Code", "Employee Name"], as_index=False).agg(
        Present_Days=("Date", "nunique"),
        OT_Hours=("OT Hours Decimal", "sum"),
    )
    emp = employee_master.copy() if not employee_master.empty else pd.DataFrame(columns=["employee_code", "employee_name", "category", "extra_wages", "extra_allowance", "deduction", "remarks"])
    emp = emp.rename(columns={"employee_code":"Employee Code", "employee_name":"Master Name", "category":"Category", "extra_wages":"Extra Wages", "extra_allowance":"Extra Allowance", "deduction":"Deduction", "remarks":"Remarks"})
    result = attendance.merge(emp, on="Employee Code", how="left")
    result["Employee Name"] = result["Employee Name"].fillna(result.get("Master Name", ""))
    result["Category"] = result["Category"].fillna("General")
    cats = categories.rename(columns={
        "category":"Category", "monthly_salary":"Monthly Salary", "working_days":"Working Days",
        "daily_wage":"Daily Wage", "ot_rate":"OT Rate", "attendance_allowance":"Attendance Allowance",
        "food_allowance":"Food Allowance", "travel_allowance":"Travel Allowance", "other_allowance":"Other Allowance"
    })
    result = result.merge(cats[["Category","Monthly Salary","Working Days","Daily Wage","OT Rate","Attendance Allowance","Food Allowance","Travel Allowance","Other Allowance"]], on="Category", how="left")
    for c in ["Monthly Salary","Working Days","Daily Wage","OT Rate","Attendance Allowance","Food Allowance","Travel Allowance","Other Allowance","Extra Wages","Extra Allowance","Deduction"]:
        if c not in result.columns:
            result[c] = 0.0
        result[c] = pd.to_numeric(result[c], errors="coerce").fillna(0.0)
    result["Daily Wage"] = result.apply(lambda r: r["Daily Wage"] if r["Daily Wage"] > 0 else (r["Monthly Salary"] / r["Working Days"] if r["Working Days"] > 0 else 0), axis=1)
    result["Regular Wages"] = result["Present_Days"] * result["Daily Wage"]
    result["OT Wages"] = result["OT_Hours"] * result["OT Rate"]
    result["Attendance Allowance Total"] = result["Present_Days"] * result["Attendance Allowance"]
    result["Food Allowance Total"] = result["Present_Days"] * result["Food Allowance"]
    result["Travel Allowance Total"] = result["Present_Days"] * result["Travel Allowance"]
    result["Other Allowance Total"] = result["Other Allowance"]
    result["Gross Wages"] = (result["Regular Wages"] + result["OT Wages"] + result["Attendance Allowance Total"] + result["Food Allowance Total"] + result["Travel Allowance Total"] + result["Other Allowance Total"] + result["Extra Wages"] + result["Extra Allowance"])
    result["Net Payable"] = result["Gross Wages"] - result["Deduction"]
    result = result.rename(columns={"Present_Days":"Present Days", "OT_Hours":"OT Hours"})
    cols = ["Employee Code","Employee Name","Category","Present Days","Daily Wage","Regular Wages","OT Hours","OT Rate","OT Wages","Attendance Allowance Total","Food Allowance Total","Travel Allowance Total","Other Allowance Total","Extra Wages","Extra Allowance","Gross Wages","Deduction","Net Payable","Remarks"]
    return result[cols].sort_values(["Category","Employee Code"])

def money(x):
    return f"₹{float(x):,.2f}"

def export_excel(sheets):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        for name, data in sheets.items():
            data.to_excel(writer, index=False, sheet_name=name[:31])
    bio.seek(0)
    return bio

# ============================================================
# PREMIUM LOGIN SCREEN
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.full_name = ""

if not st.session_state.logged_in:
    st.markdown("""
    <style>
    .login-wrap { max-width: 440px; margin: 6vh auto; padding: 40px; border-radius: 20px; background: #ffffff; border: 1px solid #e2e8f0; box-shadow: 0 15px 35px rgba(0,0,0,0.08); }
    .login-logo { font-size: 48px; text-align: center; margin-bottom: 10px; }
    .login-title { text-align: center; font-size: 26px; font-weight: 700; color: #1e293b; }
    .login-sub { text-align: center; color: #64748b; margin-bottom: 30px; font-size: 14px; }
    </style>
    <div class="login-wrap">
        <div class="login-logo">💼</div>
        <div class="login-title">HR Payroll Portal</div>
        <div class="login-sub">Secure Attendance, Overtime & Wage System</div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        u_input = st.text_input("Username")
        p_input = st.text_input("Password", type="password")
        submit = st.form_submit_button("🔐 Secure Login", use_container_width=True)
        if submit:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT password_hash, role, full_name FROM users WHERE username=?", (u_input.strip(),))
            row = cur.fetchone()
            conn.close()
            if row and row[0] == hash_password(p_input):
                st.session_state.logged_in = True
                st.session_state.username = u_input.strip()
                st.session_state.role = row[1]
                st.session_state.full_name = row[2]
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password.")
    st.stop()

# ============================================================
# ROLE-BASED NAVIGATION SETUP
# ============================================================
role = st.session_state.role

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
div[data-testid="stMetric"] { background: #fff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("💼 HR Payroll Portal")
st.sidebar.markdown(f"**Welcome, {st.session_state.full_name}**  \n*Role: {role}*")
st.sidebar.divider()

pages_map = {
    "Admin": [
        "📊 HR Dashboard", "👥 Employee Management", "📋 Attendance Management",
        "⏱️ Overtime Management", "💰 Salary & Wages", "⚙️ Salary Master",
        "📑 Reports & Excel Export", "⚙️ User Management", "📤 Upload Data"
    ],
    "HR": [
        "📊 HR Dashboard", "👥 Employee Management", "📋 Attendance Management",
        "📑 Reports & Excel Export", "📤 Upload Data"
    ],
    "Accounts": [
        "📊 HR Dashboard", "💰 Salary & Wages", "⚙️ Salary Master",
        "📑 Reports & Excel Export"
    ],
    "Supervisor": [
        "📋 Attendance Management", "⏱️ Overtime Management"
    ],
    "Employee": [
        "👤 Employee View"
    ]
}

available_pages = pages_map.get(role, ["📊 HR Dashboard"])
page = st.sidebar.radio("Navigation", available_pages)
st.sidebar.divider()

duty_hours = st.sidebar.number_input("Standard Duty Hours / Day", min_value=1.0, max_value=24.0, value=8.0, step=0.5)

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.full_name = ""
    st.rerun()

# ============================================================
# LOAD APP DATA
# ============================================================
df = load_data()
categories = load_categories()
employee_master = load_employee_salary()

if not df.empty:
    normalized_db = df.rename(columns={
        "transaction_date":"Transaction Date", "punch_time":"Time", "department":"Department",
        "employee_code":"Employee Code", "employee_name":"Employee Name", "location_name":"Location Name",
        "entry_exit":"ENTRY/EXIT"
    })
    normalized_db["Time Parsed"] = normalized_db["Time"].apply(parse_time)
    normalized_db["ENTRY/EXIT"] = normalized_db["ENTRY/EXIT"].apply(normalize_direction)
    daily = build_daily_report(normalized_db, duty_hours)
else:
    normalized_db = pd.DataFrame()
    daily = pd.DataFrame()

# ============================================================
# PAGE: UPLOAD DATA
# ============================================================
if page == "📤 Upload Data":
    st.title("📤 Upload Punching Data")
    st.info("Upload Excel/CSV punching logs. Entry/in = IN; Exit/out = OUT.")
    uploaded = st.file_uploader("Choose Excel or CSV file", type=["xlsx","xls","csv"])
    if uploaded:
        try:
            if uploaded.name.lower().endswith(".csv"):
                raw = pd.read_csv(uploaded)
            else:
                book = pd.ExcelFile(uploaded)
                preferred = next((s for s in book.sheet_names if "punch" in s.lower() or "puching" in s.lower()), book.sheet_names[0])
                raw = pd.read_excel(uploaded, sheet_name=preferred)
            normalized = normalize_punching(raw)
            st.success(f"Detected {len(normalized):,} valid punch records.")
            st.dataframe(normalized.drop(columns=["Time Parsed"], errors="ignore").head(50), use_container_width=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📥 Import & Append Records", type="primary", use_container_width=True):
                    n, dups = insert_punching_data(normalized)
                    st.success(f"Successfully imported {n:,} records. Duplicates skipped: {dups:,}.")
                    st.rerun()
            with c2:
                if st.button("🗑️ Clear All Punching Data", use_container_width=True):
                    clear_punching_data()
                    st.warning("All punching logs cleared.")
                    st.rerun()
        except Exception as e:
            st.error(f"Import error: {e}")

# ============================================================
# PAGE: HR DASHBOARD
# ============================================================
elif page == "📊 HR Dashboard":
    st.title("📊 HR Attendance & Payroll Dashboard")
    if df.empty:
        st.info("No punching data available. Go to Upload Data to import attendance records.")
    else:
        c = st.columns(5)
        c[0].metric("Total Punches", f"{len(df):,}")
        c[1].metric("Employees", f"{df['employee_code'].nunique():,}")
        c[2].metric("Present Days Logged", f"{daily.shape[0]:,}")
        ot_total = sum(hours_float(pd.to_timedelta(x)) for x in daily["OT Hours"]) if not daily.empty else 0
        c[3].metric("Total OT Hours", f"{ot_total:,.2f}")
        c[4].metric("Salary Categories", f"{categories['category'].nunique():,}")
        
        st.subheader("Recent Punch Activity")
        st.dataframe(df.head(50), use_container_width=True, hide_index=True)

# ============================================================
# PAGE: EMPLOYEE MANAGEMENT
# ============================================================
elif page == "👥 Employee Management":
    st.title("👥 Employee Management")
    st.caption("Manage employee directory, active categories, and personal allowances.")
    if df.empty and employee_master.empty:
        st.info("No employee records found. Upload punching data or add employee salary configurations.")
    else:
        q = st.text_input("Search Employee Code / Name")
        emp_list = employee_master.copy()
        if not df.empty:
            active_emps = df[["employee_code", "employee_name"]].drop_duplicates().rename(columns={"employee_code":"Employee Code", "employee_name":"Employee Name"})
            if emp_list.empty:
                emp_list = active_emps.rename(columns={"Employee Code":"employee_code", "Employee Name":"employee_name"})
            else:
                emp_list = active_emps.merge(emp_list, left_on="Employee Code", right_on="employee_code", how="outer")
                emp_list["employee_code"] = emp_list["employee_code"].fillna(emp_list["Employee Code"])
                emp_list["employee_name"] = emp_list["employee_name"].fillna(emp_list["Employee Name"])
        if q and not emp_list.empty:
            mask = emp_list["employee_code"].astype(str).str.contains(q, case=False, na=False) | emp_list["employee_name"].astype(str).str.contains(q, case=False, na=False)
            emp_list = emp_list[mask]
        st.dataframe(emp_list, use_container_width=True, hide_index=True)

# ============================================================
# PAGE: ATTENDANCE MANAGEMENT
# ============================================================
elif page == "📋 Attendance Management":
    st.title("📋 Attendance Management")
    if daily.empty:
        st.info("No attendance data available.")
    else:
        st.caption("First IN and Last OUT per employee/date calculation rule applied.")
        st.dataframe(daily, use_container_width=True, hide_index=True)
        
        st.subheader("Attendance Matrix")
        att = daily.pivot_table(index=["Employee Code","Employee Name"], columns="Date", values="Status", aggfunc="first")
        att = att.map(lambda x: 1 if x == "Present" else 0)
        att["Grand Total"] = att.sum(axis=1)
        st.dataframe(att, use_container_width=True)

# ============================================================
# PAGE: OVERTIME MANAGEMENT
# ============================================================
elif page == "⏱️ Overtime Management":
    st.title("⏱️ Overtime Management")
    if daily.empty:
        st.info("No attendance data available.")
    else:
        ot = daily.copy()
        ot["OT Hours Decimal"] = ot["OT Hours"].apply(lambda x: hours_float(pd.to_timedelta(x)))
        otm = ot.pivot_table(index=["Employee Code","Employee Name"], columns="Date", values="OT Hours Decimal", aggfunc="sum", fill_value=0)
        otm["OT Grand Total Hours"] = otm.sum(axis=1)
        st.subheader("Overtime (OT) Matrix (Hours)")
        st.dataframe(otm, use_container_width=True)

# ============================================================
# PAGE: SALARY MASTER
# ============================================================
elif page == "⚙️ Salary Master":
    st.title("⚙️ Salary & Wage Master")
    st.caption("Configure category-wise rates and employee-specific adjustments.")
    
    with st.form("category_form"):
        c1, c2, c3, c4 = st.columns(4)
        cat = c1.text_input("Category Name", placeholder="Skilled / Unskilled")
        monthly = c2.number_input("Monthly Salary", min_value=0.0, step=100.0)
        workdays = c3.number_input("Working Days / Month", min_value=1.0, value=26.0, step=1.0)
        daily_rate = c4.number_input("Daily Wage (0 = Auto)", min_value=0.0, step=10.0)
        
        c5, c6, c7, c8 = st.columns(4)
        ot_rate = c5.number_input("OT Rate / Hour", min_value=0.0, step=10.0)
        att_allow = c6.number_input("Attendance Allowance / Day", min_value=0.0, step=10.0)
        food = c7.number_input("Food Allowance / Day", min_value=0.0, step=10.0)
        travel = c8.number_input("Travel Allowance / Day", min_value=0.0, step=10.0)
        other = st.number_input("Other Monthly Allowance", min_value=0.0, step=50.0)
        
        if st.form_submit_button("💾 Save / Update Category", type="primary"):
            if not cat.strip():
                st.error("Enter category name.")
            else:
                effective_daily = daily_rate if daily_rate > 0 else (monthly / workdays if workdays else 0)
                save_category((cat.strip(), monthly, workdays, effective_daily, ot_rate, att_allow, food, travel, other))
                st.success("Category saved successfully.")
                st.rerun()
                
    st.subheader("Existing Categories")
    cats_show = load_categories()
    st.dataframe(cats_show, use_container_width=True, hide_index=True)

# ============================================================
# PAGE: SALARY & WAGES
# ============================================================
elif page == "💰 Salary & Wages":
    st.title("💰 Salary & Wages Calculation")
    st.caption("Regular wages + OT wages + Allowances + Extras - Deductions = Net Payable.")
    if daily.empty:
        st.info("Import punching data first.")
    else:
        date_series = pd.to_datetime(daily["Date"])
        min_d, max_d = date_series.min().date(), date_series.max().date()
        c1, c2, c3 = st.columns(3)
        from_d = c1.date_input("From Date", min_d)
        to_d = c2.date_input("To Date", max_d)
        selected_cat = c3.selectbox("Category Filter", ["All"] + categories["category"].tolist())
        
        if from_d > to_d:
            st.error("From Date cannot be after To Date.")
        else:
            period_daily = daily[(pd.to_datetime(daily["Date"]).dt.date >= from_d) & (pd.to_datetime(daily["Date"]).dt.date <= to_d)].copy()
            if selected_cat != "All":
                codes = employee_master.query("category == @selected_cat")["employee_code"].astype(str).tolist()
                period_daily = period_daily[period_daily["Employee Code"].astype(str).isin(codes)]
            
            salary = build_salary_report(period_daily, categories, employee_master)
            if salary.empty:
                st.warning("No records found for selected period/category.")
            else:
                c = st.columns(5)
                c[0].metric("Employees", len(salary))
                c[1].metric("Present Days", int(salary["Present Days"].sum()))
                c[2].metric("Regular Wages", money(salary["Regular Wages"].sum()))
                c[3].metric("OT Wages", money(salary["OT Wages"].sum()))
                c[4].metric("Net Payable", money(salary["Net Payable"].sum()))
                
                st.subheader("Employee Salary Breakdown")
                st.dataframe(salary, use_container_width=True, hide_index=True)
                
                xlsx = export_excel({"Salary Wages": salary, "Daily Attendance": period_daily})
                st.download_button("📥 Download Salary Excel", xlsx, file_name=f"Salary_Report_{from_d}_{to_d}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ============================================================
# PAGE: REPORTS & EXCEL EXPORT
# ============================================================
elif page == "📑 Reports & Excel Export":
    st.title("📑 Reports & Excel Export")
    if daily.empty:
        st.info("No data available for export.")
    else:
        att = daily.pivot_table(index=["Employee Code","Employee Name"], columns="Date", values="Status", aggfunc="first")
        att = att.map(lambda x: 1 if x == "Present" else 0)
        att["Grand Total"] = att.sum(axis=1)
        
        ot = daily.copy()
        ot["OT Hours Decimal"] = ot["OT Hours"].apply(lambda x: hours_float(pd.to_timedelta(x)))
        otm = ot.pivot_table(index=["Employee Code","Employee Name"], columns="Date", values="OT Hours Decimal", aggfunc="sum", fill_value=0)
        otm["OT Grand Total Hours"] = otm.sum(axis=1)
        
        salary = build_salary_report(daily, categories, employee_master)
        xlsx = export_excel({
            "Daily Attendance": daily,
            "Attendance Matrix": att.reset_index(),
            "OT Matrix": otm.reset_index(),
            "Salary Wages": salary
        })
        st.download_button("📥 Download Complete HR Report (Excel)", xlsx, file_name="Complete_HR_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ============================================================
# PAGE: USER MANAGEMENT (Admin Only)
# ============================================================
elif page == "⚙️ User Management":
    st.title("⚙️ User Management")
    st.caption("Manage system users and role permissions (Admin, HR, Accounts, Supervisor, Employee).")
    
    with st.form("user_form"):
        c1, c2 = st.columns(2)
        new_user = c1.text_input("Username")
        new_pass = c2.text_input("Password", type="password")
        c3, c4 = st.columns(2)
        new_role = c3.selectbox("Role", ["Admin", "HR", "Accounts", "Supervisor", "Employee"])
        new_fname = c4.text_input("Full Name")
        
        if st.form_submit_button("💾 Save / Create User", type="primary"):
            if not new_user.strip() or not new_pass.strip():
                st.error("Username and password required.")
            else:
                save_user(new_user.strip(), new_pass.strip(), new_role, new_fname.strip())
                st.success(f"User {new_user} saved successfully.")
                st.rerun()
                
    st.subheader("Existing System Users")
    st.dataframe(load_users(), use_container_width=True, hide_index=True)

# ============================================================
# PAGE: EMPLOYEE VIEW
# ============================================================
elif page == "👤 Employee View":
    st.title("👤 My Attendance & Salary View")
    st.info("Logged in as employee view. You can review your attendance records.")
    if daily.empty:
        st.info("No attendance records found.")
    else:
        my_code = st.text_input("Enter your Employee Code to view records:")
        if my_code:
            x = daily[daily["Employee Code"].astype(str) == my_code.strip()].copy()
            if x.empty:
                st.warning("No records found for this employee code.")
            else:
                st.success(f"Found records for {x['Employee Name'].iloc[0]}")
                st.dataframe(x, use_container_width=True, hide_index=True)
