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
# DATABASE CONNECTION (Fixed: Uncached to prevent connection errors)
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
    conn = get_connection()
    cur = conn.cursor()
    inserted = 0
    duplicates = 0
    for _, row in data.iterrows():
        try:
            cur.execute("""
                INSERT OR IGNORE INTO punching_data
                (transaction_date, punch_time, department, employee_code,
                 employee_name, location_name, entry_exit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row["Transaction Date"]), str(row["Time"]),
                str(row["Department"]), str(row["Employee Code"]),
                str(row["Employee Name"]), str(row["Location Name"]),
                str(row["ENTRY/EXIT"]),
            ))
            if cur.rowcount == 1:
                inserted += 1
            else:
                duplicates += 1
        except Exception:
            duplicates += 1
    conn.commit()
    conn.close()
    st.cache_data.clear()
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
    .login-sub { text-align: center;
