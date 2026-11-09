# 📊 Advanced Attendance & OT Portal v2.0

## 🎉 What's New

✅ **Mixed Entry/Exit Support** - Handle entry, exit, in, out all together  
✅ **Proper IN/OUT Calculation** - First IN to Last OUT matching  
✅ **Multi-Sheet Excel Import** - Import multiple months at once  
✅ **Login System** - Secure authentication with roles  
✅ **Smart Column Detection** - Auto-finds your columns  
✅ **Data Preview** - See normalization before import  

---

## 📁 Files in This Folder

### 🚀 Main Application
**`Attendance_Portal_Updated.py`** ← **RUN THIS FILE**
- Complete attendance and OT management system
- Login with demo credentials
- Upload Excel files with multiple sheets
- Dashboard with real-time analytics

### 📖 Documentation
**`SETUP_GUIDE.md`** - Complete setup and usage guide
- Installation instructions
- Excel format examples
- Feature descriptions
- Troubleshooting tips

**`NORMALIZATION_GUIDE.txt`** - Entry/Exit value conversion guide
- Shows all supported values
- Examples of transformations
- How calculations work
- Tips for success

**`requirements.txt`** - Python package dependencies
- Lists all required libraries
- Use: `pip install -r requirements.txt`

---

## ⚡ Quick Start

### 1. Install Dependencies
```bash
pip install streamlit pandas openpyxl plotly
```

### 2. Run the App
```bash
streamlit run Attendance_Portal_Updated.py
```

### 3. Login
```
Username: admin
Password: admin123
```

### 4. Upload Your Excel
- Click "📥 Data Upload"
- Select your Excel file with multiple sheets
- Preview the data
- Click "Import All Sheets"

---

## 📋 Excel Format

Your Excel file should have columns like:

| Transaction Date | Time | Employee Code | IN/OUT | Employee Name | Department |
|---|---|---|---|---|---|
| 01-01-2024 | 09:15:00 | EMP001 | entry | John Doe | Sales |
| 01-01-2024 | 17:45:00 | EMP001 | exit | John Doe | Sales |
| 02-01-2024 | 09:20:00 | EMP001 | in | John Doe | Sales |
| 02-01-2024 | 18:00:00 | EMP001 | out | John Doe | Sales |

**Key Points:**
- Can have multiple sheets (one per month)
- Column names can be flexible (date, Date, DATE all work)
- IN/OUT column can have mixed values (entry, exit, in, out)
- Employee Name & Department are optional

---

## 🔐 Login Credentials

### Admin
- Username: `admin`
- Password: `admin123`
- Can: View all data, Upload files, Clear data

### User
- Username: `user`
- Password: `user123`
- Can: View reports, Export data, View analytics

---

## 🎯 Key Features

### 📊 Dashboard
- Total employees & days recorded
- Total OT hours summary
- Top 10 employees by OT
- Daily OT trends
- Department-wise analysis
- Real-time anomaly alerts

### 📥 Data Upload
- Multi-sheet Excel import
- CSV support
- Column auto-detection
- Data preview with normalization
- Progress tracking

### 📋 Punching Data
- Raw transaction view
- Filter by employee, type, department
- Export to Excel

### ⏱️ Daily Report
- First IN & Last OUT times
- Working hours calculated
- OT hours computed
- Attendance status
- Excel download

### 👤 Employee Profiles
- Individual performance cards
- Total OT summary
- Average working hours
- Attendance history

### 🚨 Anomalies
- Missing IN detection
- Missing OUT detection
- Excessive hours alert
- Filter by severity

### 📊 Analytics
- Late arrival tracking
- OT trend analysis
- Statistical summaries

---

## 🔧 How Entry/Exit Normalization Works

### Input → Output Conversion

All these values in your Excel...
```
entry    → IN
exit     → OUT
in       → IN
out      → OUT
ENTRY    → IN
EXIT     → OUT
Entry    → IN
Exit     → OUT
entry    → IN (from another column)
exit     → OUT (from another column)
```

...become consistent IN/OUT values in the system!

### Working Time Calculation
```
First IN   = Earliest entry/in punch
Last OUT   = Latest exit/out punch
Working Minutes = Last OUT - First IN
OT Minutes = Working Minutes - (8 hours × 60)
```

---

## ✨ Important Features

✅ **Flexible Column Names** - App finds your columns automatically  
✅ **Mixed Values Support** - Handle entry/exit AND in/out together  
✅ **Data Validation** - Preview shows normalization before import  
✅ **Anomaly Detection** - Auto-detects missing punches & errors  
✅ **Export Ready** - Download reports as Excel  
✅ **Multi-sheet Import** - Upload entire month of data at once  
✅ **User Management** - Login with different roles  
✅ **Real-time Analytics** - Charts and trends  

---

## 📊 Database

Data is stored locally in:
- `attendance_advanced.db` (SQLite)
- Created automatically on first run
- All data stays on your computer
- No internet connection needed

---

## 🛠️ Troubleshooting

### Issue: Column not found
**Solution:** Check column names match the examples (Transaction Date, Time, Employee Code, IN/OUT)

### Issue: Working hours incorrect
**Solution:** Ensure:
- Date format is DD-MM-YYYY or YYYY-MM-DD
- Time format is HH:MM or HH:MM:SS
- Each employee has IN and OUT punches

### Issue: Import not working
**Solution:** Check preview before import to see which columns were detected

### Issue: Login fails
**Solution:** Use demo credentials: admin / admin123

---

## 📈 Reports Available

1. **Daily Report** - Working hours, OT per day
2. **Employee Profiles** - Individual performance
3. **Anomaly Report** - Missing punches, errors
4. **Analytics** - Trends, late arrivals, statistics

All reports can be exported to Excel!

---

## 💡 Tips

1. Clean your Excel before upload (remove extra rows)
2. Use consistent date & time formats
3. Review data preview before importing
4. Check anomaly alerts after upload
5. Export reports regularly for backup
6. Use Admin account for first-time setup

---

## 📝 File Descriptions

| File | Purpose |
|---|---|
| Attendance_Portal_Updated.py | Main application - RUN THIS |
| SETUP_GUIDE.md | Complete documentation |
| NORMALIZATION_GUIDE.txt | Entry/Exit conversion guide |
| requirements.txt | Python dependencies |
| README.md | This file |

---

## 🎉 Ready to Use!

1. ✅ Install packages: `pip install -r requirements.txt`
2. ✅ Run app: `streamlit run Attendance_Portal_Updated.py`
3. ✅ Login with: admin / admin123
4. ✅ Upload your Excel file
5. ✅ View instant analytics!

---

## 📞 Need Help?

- Check **SETUP_GUIDE.md** for detailed instructions
- Check **NORMALIZATION_GUIDE.txt** for entry/exit handling
- Preview your Excel data before importing
- Review anomaly alerts after upload

---

**Version:** 2.0  
**Last Updated:** January 2024  
**Status:** ✅ Ready to Use

Enjoy your new Attendance Portal! 🚀
