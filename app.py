import streamlit as st
import pandas as pd
import base64
import os
import io
import json
import re
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
import warnings

warnings.filterwarnings("ignore")

# ==========================================
# ⚙️ PAGE CONFIG & AUTHENTICATION SETUP
# ==========================================
st.set_page_config(page_title="AMC NTEP - Adverse Outcomes", layout="wide", initial_sidebar_state="collapsed")
india_tz = pytz.timezone('Asia/Kolkata')

def img_to_b64(img_path):
    try:
        with open(img_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode('utf-8')
    except: return ""

if "auth" not in st.session_state: 
    st.session_state.auth = False
    st.session_state.current_user = ""
    st.session_state.role = ""
    st.session_state.target = ""

try:
    df_users = pd.read_csv("users.csv")
    df_users['Username'] = df_users['Username'].astype(str).str.strip().str.upper()
except:
    st.error("⚠️ User Database (users.csv) not found in the repository!")
    st.stop()

# ==========================================
# 🔐 ENTERPRISE LOGIN PAGE
# ==========================================
if not st.session_state.auth:
    b64_amc = img_to_b64("amc.png")
    
    st.markdown("""
    <style>
    .left-panel { background: #0A3A6E; color: white; padding: 40px 30px; border-radius: 15px 0 0 15px; text-align: center; height: 100%;}
    .right-panel { padding: 40px; background: white; border-radius: 0 15px 15px 0; border: 1px solid #e2e8f0; height: 100%; }
    .stTextInput>div>div>input { border-radius: 8px; border: 1px solid #cbd5e1; padding: 12px; }
    .stButton>button { background-color: #0A3A6E; color: white; border-radius: 8px; width: 100%; font-weight: 600; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    sp1, login_box, sp2 = st.columns([1, 6, 1])
    
    with login_box:
        l_col, r_col = st.columns([4, 5], gap="small")
        with l_col:
            st.markdown(f"""
            <div class="left-panel">
            <img src="data:image/png;base64,{b64_amc}" width="65" style="margin-bottom:20px; background:white; border-radius:50%; padding:5px;">
            <h2 style="font-size: 24px; font-weight: 600;">AMC · NTEP</h2>
            <p style="font-size: 13px; color: #85B7EB;">Adverse Outcomes & Field Entry Module</p>
            </div>
            """, unsafe_allow_html=True)
            
        with r_col:
            st.markdown("<h3 style='color: #1e293b; font-weight: 600;'>Sign in</h3><br>", unsafe_allow_html=True)
            uname = st.text_input("User ID / Zone Code").strip().upper()
            pwd = st.text_input("Password", type="password").strip()
            
            if st.button("Sign In Securely"):
                user_match = df_users[(df_users['Username'] == uname) & (df_users['Password'].astype(str).str.strip() == pwd)]
                if not user_match.empty: 
                    st.session_state.auth = True
                    st.session_state.current_user = uname
                    st.session_state.role = str(user_match.iloc[0]['Role']).strip().upper()
                    st.session_state.target = str(user_match.iloc[0]['Target']).strip().upper()
                    st.rerun()
                else: 
                    st.error("⚠️ Invalid User ID or Password")
    st.stop()

# ==========================================
# 🟢 MAIN APPLICATION & DATABASE CONNECTIONS
# ==========================================
st.markdown(f"<div style='background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px; font-weight: bold; margin-bottom: 20px;'>👤 Logged in as: {st.session_state.target} ({st.session_state.role})</div>", unsafe_allow_html=True)

@st.cache_resource
def init_gspread():
    creds_dict = json.loads(st.secrets["google_credentials"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

client = init_gspread()
NEW_SHEET_URL = "https://docs.google.com/spreadsheets/d/11JHb7Zv4KqV_PAY9REGBVdkLwqBSubvgtSrr1ulGRzA/edit"

try:
    new_sheet = client.open_by_url(NEW_SHEET_URL).sheet1
except Exception as e:
    st.error("Could not connect to the New Google Sheet. Check permissions and URL.")
    st.stop()

# Fetch Live Data (New Sheet for Line List & Data Entry)
@st.cache_data(ttl=10, show_spinner="Syncing Live Data Tracker...")
def get_live_tracker():
    try:
        return pd.DataFrame(new_sheet.get_all_records())
    except:
        return pd.DataFrame()

df_live = get_live_tracker()

# Fetch KPIs (Old Sheet for denominators)
@st.cache_data(ttl=600, show_spinner="Calculating Executive Metrics...")
def load_kpi_data():
    import urllib.request
    try:
        url = "https://docs.google.com/spreadsheets/d/1Dfvl87uaZZ12_5F4dhHXTP_u8i9NM9TASWN8wyX18nE/export?format=csv&gid=1898426568"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            return pd.read_csv(io.BytesIO(response.read()), low_memory=False, dtype=str, on_bad_lines='skip')
    except:
        return pd.DataFrame()

df_this_raw = load_kpi_data()

# ---------------------------------------------------------
# 🧮 CALCULATION ENGINE: YEAR-WISE SUCCESS & DEATH RATES
# ---------------------------------------------------------
success_overall_str, success_years_str = "0%", ""
death_overall_str, death_years_str = "0%", ""
init_death_overall_str, init_death_years_str = "0%", ""

if not df_this_raw.empty:
    def cx(col_letter):
        num = 0
        for c in col_letter.upper(): num = num * 26 + (ord(c) - ord('A') + 1)
        return num - 1

    def get_col_series(df, possible_names, fallback_col_letter):
        for p in possible_names:
            p_clean = re.sub(r'[^A-Z0-9]', '', str(p).upper())
            for c in df.columns:
                c_clean = re.sub(r'[^A-Z0-9]', '', str(c).upper())
                if c_clean == p_clean: return df[c]
        idx = cx(fallback_col_letter)
        if idx < len(df.columns): return df.iloc[:, idx]
        return pd.Series([""] * len(df))

    ep_series = get_col_series(df_this_raw, ['EPISODE ID'], 'M').fillna("").astype(str).str.strip()
    regimen_series = get_col_series(df_this_raw, ['TYPE OF TB REGIMEN'], 'BJ').fillna("").astype(str).str.upper()
    outcome_series = get_col_series(df_this_raw, ['TREATMENT OUTCOME'], 'BK').fillna("").astype(str).str.upper().str.strip()
    
    diag_series = get_col_series(df_this_raw, ['DIAGNOSIS DATE'], 'S').fillna("").astype(str).str.strip()
    init_series = get_col_series(df_this_raw, ['INITIATION DATE'], 'BM').fillna("").astype(str).str.strip()
    out_date_series = get_col_series(df_this_raw, ['OUTCOME DATE'], 'CB').fillna("").astype(str).str.strip()

    df_calc = pd.DataFrame({
        'Valid': ~ep_series.isin(["", "NAN", "NONE", "NULL", "N/A"]),
        'Regimen_Eligible': regimen_series.str.contains("2HRZE/4HRE|2HRZES|4HRE|2HRZE", regex=True, na=False),
        'Is_Success': outcome_series.str.contains("COMPLETE|CURED", regex=True, na=False),
        'Is_Death': outcome_series.str.contains("DIED|DEATH", regex=True, na=False),
        'Init_Year': pd.to_datetime(init_series, errors='coerce').dt.year,
        'Diag_Year': pd.to_datetime(diag_series, errors='coerce').dt.year,
        'Has_Diag': diag_series != "",
        'Has_OutDate': out_date_series != "",
        'No_Init': init_series == ""
    })

    df_calc_init = df_calc[df_calc['Valid'] & df_calc['Regimen_Eligible']].copy()
    total_eligible = len(df_calc_init)
    
    if total_eligible > 0:
        success_overall_str = f"{(df_calc_init['Is_Success'].sum() / total_eligible * 100):.1f}%"
        death_overall_str = f"{(df_calc_init['Is_Death'].sum() / total_eligible * 100):.1f}%"
        
        grp_succ = df_calc_init.groupby('Init_Year')['Is_Success'].agg(['sum', 'count'])
        grp_death = df_calc_init.groupby('Init_Year')['Is_Death'].agg(['sum', 'count'])
        success_years_str = " | ".join([f"{int(y)}: {(r['sum']/r['count']*100):.1f}%" for y, r in grp_succ.iterrows() if pd.notna(y) and r['count'] > 0])
        death_years_str = " | ".join([f"{int(y)}: {(r['sum']/r['count']*100):.1f}%" for y, r in grp_death.iterrows() if pd.notna(y) and r['count'] > 0])

    df_calc_diag = df_calc[df_calc['Valid']].copy()
    df_calc_diag['Is_Initial_Death'] = df_calc_diag['Has_Diag'] & df_calc_diag['Has_OutDate'] & df_calc_diag['No_Init'] & df_calc_diag['Is_Death']
    
    total_diag = len(df_calc_diag)
    if total_diag > 0:
        init_death_overall_str = f"{(df_calc_diag['Is_Initial_Death'].sum() / total_diag * 100):.1f}%"
        grp_init = df_calc_diag.groupby('Diag_Year')['Is_Initial_Death'].agg(['sum', 'count'])
        init_death_years_str = " | ".join([f"{int(y)}: {(r['sum']/r['count']*100):.1f}%" for y, r in grp_init.iterrows() if pd.notna(y) and r['count'] > 0])

# Calculate Live Metrics
total_adverse_count = len(df_live)
ahmedabad_pct_str = "0%"
if total_adverse_count > 0 and 'ZONE' in df_live.columns:
    ahmedabad_mask = df_live['ZONE'].astype(str).str.upper().str.contains("AHMEDABAD|EAST|WEST|NORTH|SOUTH|CENTRAL|AMC", regex=True, na=False)
    ahmedabad_pct_str = f"{int((ahmedabad_mask.sum() / total_adverse_count) * 100)}%"

# ==========================================
# 📊 EXECUTIVE SUMMARY (MOH VIEW)
# ==========================================
st.markdown("""
<style>
    .kpi-card { background-color: #0A3A6E; color: white; padding: 18px 10px; border-radius: 8px; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center;}
    .kpi-title { font-size: 11px; text-transform: uppercase; font-weight: 700; opacity: 0.9; }
    .kpi-value { font-size: 26px; font-weight: 900; margin-top: 5px; }
    .kpi-sub { font-size: 10px; color: #cbd5e1; margin-top: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>📊 Executive Summary</h3>", unsafe_allow_html=True)
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

with kpi1: st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Total Adverse Outcomes</div><div class='kpi-value'>{total_adverse_count}</div></div>", unsafe_allow_html=True)
with kpi2: st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Ahmedabad Residents</div><div class='kpi-value'>{ahmedabad_pct_str}</div></div>", unsafe_allow_html=True)
with kpi3: st.markdown(f"<div class='kpi-card' style='background-color: #16a34a;'><div class='kpi-title'>Success Rate</div><div class='kpi-value'>{success_overall_str}</div><div class='kpi-sub'>{success_years_str}</div></div>", unsafe_allow_html=True)
with kpi4: st.markdown(f"<div class='kpi-card' style='background-color: #f97316;'><div class='kpi-title'>Initial Death Rate</div><div class='kpi-value'>{init_death_overall_str}</div><div class='kpi-sub'>{init_death_years_str}</div></div>", unsafe_allow_html=True)
with kpi5: st.markdown(f"<div class='kpi-card' style='background-color: #dc2626;'><div class='kpi-title'>Normal Death Rate</div><div class='kpi-value'>{death_overall_str}</div><div class='kpi-sub'>{death_years_str}</div></div>", unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid #cbd5e1; margin: 25px 0;'>", unsafe_allow_html=True)

# ==========================================
# ⚡ FAST FIELD STAFF DATA ENTRY (DROPDOWN)
# ==========================================
st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>⚡ Fast Field Data Entry</h3>", unsafe_allow_html=True)

if not df_live.empty:
    if 'Addiction' not in df_live.columns:
        st.error("⚠️ Setup Required: Please add the following column headers to your Google Sheet starting at Column Q: 'Addiction', 'Comorbidity', 'Migration', 'Remarks', 'Submitted By', 'Timestamp'.")
    else:
        # Filter for the staff's specific TB Unit
        df_staff_pending = df_live.copy()
        if st.session_state.role in ["TB_UNIT", "TU"]:
            staff_tu = st.session_state.target.strip().upper()
            df_staff_pending = df_staff_pending[df_staff_pending['TB Unit'].astype(str).str.upper().str.contains(staff_tu, na=False)]
            
        # Isolate ONLY patients who haven't been entered yet
        df_pending_only = df_staff_pending[df_staff_pending['Addiction'].fillna("").astype(str).str.strip() == ""]
        
        if df_pending_only.empty:
            st.success("🎉 All caught up! There are no pending adverse outcomes for your area.")
        else:
            st.markdown("<div style='font-size: 14px; margin-bottom:15px; color:#555;'>Select a pending patient from your area to log their root cause details. The list updates automatically.</div>", unsafe_allow_html=True)
            
            # Create Dropdown Options
            options = df_pending_only.apply(lambda x: f"{x['Episode ID']} - {x['Patient Name']} ({x['Treatment Outcome']})", axis=1).tolist()
            options.insert(0, "-- Select a Patient --")
            
            selected_patient = st.selectbox("⏳ Pending Patients:", options)
            
            if selected_patient != "-- Select a Patient --":
                active_id = selected_patient.split(" - ")[0].strip()
                p_info = df_pending_only[df_pending_only['Episode ID'].astype(str) == active_id].iloc[0]
                
                with st.form("fast_entry_form", clear_on_submit=True):
                    st.write(f"**Logging details for:** {p_info['Patient Name']} | **Zone:** {p_info['ZONE']}")
                    
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        addiction = st.selectbox("Does the patient have any addiction?", ["Select", "YES - Alcohol", "YES - Tobacco", "YES - Multiple", "NO"])
                        comorbidity = st.selectbox("Known Comorbidities?", ["Select", "Diabetes", "HIV", "Hypertension", "None", "Other"])
                    with fc2:
                        migration = st.selectbox("Is the patient a migratory resident?", ["Select", "YES - Native outside Ahmedabad", "NO - Local Resident"])
                        staff_notes = st.text_area("Field Staff Remarks / Cause Summary")

                    submit_btn = st.form_submit_button("💾 Save to Master Database", use_container_width=True)

                    if submit_btn:
                        if "Select" in [addiction, comorbidity, migration]:
                            st.error("⚠️ Please answer all dropdown questions before submitting.")
                        else:
                            timestamp = datetime.now(india_tz).strftime("%d-%b-%Y %H:%M:%S")
                            
                            try:
                                # Look up exact row by Episode ID (Assuming it is Column H / Index 8)
                                cell = new_sheet.find(active_id, in_column=8)
                                
                                # Highly secure cell update targeting columns Q through V
                                cells_to_update = new_sheet.range(f'Q{cell.row}:V{cell.row}')
                                new_vals = [addiction, comorbidity, migration, staff_notes, st.session_state.current_user, timestamp]
                                
                                for i, val in enumerate(new_vals):
                                    cells_to_update[i].value = new_vals[i]
                                
                                new_sheet.update_cells(cells_to_update)
                                
                                st.success(f"🎉 Success! Data for {active_id} saved.")
                                get_live_tracker.clear() # Clear cache to instantly remove them from the dropdown
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error updating row in Google Sheet. Make sure Episode ID is in Column H. Error: {e}")

st.markdown("<hr style='border: 1px solid #cbd5e1; margin: 25px 0;'>", unsafe_allow_html=True)

# ==========================================
# 📋 MASTER ADVERSE OUTCOMES DATA TABLE
# ==========================================
st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>📋 Full Integrated Line List</h3>", unsafe_allow_html=True)
st.markdown("<div style='font-size: 13px; color: #555; margin-bottom: 15px;'><i>This table displays your original master data on the left, seamlessly merged with the new field data entries on the right.</i></div>", unsafe_allow_html=True)

if not df_live.empty:
    df_display = df_live.copy()
    
    # Filter by user role for the Line List view
    if st.session_state.role in ["TB_UNIT", "TU"]:
        df_display = df_display[df_display['TB Unit'].astype(str).str.upper().str.contains(st.session_state.target.strip().upper(), na=False)]
    elif st.session_state.role == "ZONE":
        df_display = df_display[df_display['ZONE'].astype(str).str.upper().str.contains(st.session_state.target.replace("ZONE", "").strip().upper(), na=False)]

    f1, f2, f3 = st.columns(3)
    with f1:
        opts_out = sorted([x for x in df_display['Treatment Outcome'].unique() if str(x).strip() != ""]) if 'Treatment Outcome' in df_display.columns else []
        sel_out = st.multiselect("Filter by Treatment Outcome", opts_out)
    with f2:
        opts_zone = sorted([x for x in df_display['ZONE'].unique() if str(x).strip() != ""]) if 'ZONE' in df_display.columns else []
        sel_zone = st.multiselect("Filter by Zone", opts_zone)
    with f3:
        # Filter by Pending or Completed Entries
        entry_status = st.selectbox("Data Entry Status", ["All", "Pending Entry", "Completed"])

    if sel_out and 'Treatment Outcome' in df_display.columns: df_display = df_display[df_display['Treatment Outcome'].isin(sel_out)]
    if sel_zone and 'ZONE' in df_display.columns: df_display = df_display[df_display['ZONE'].isin(sel_zone)]
    
    if entry_status == "Pending Entry" and 'Addiction' in df_display.columns:
        df_display = df_display[df_display['Addiction'].astype(str).str.strip() == ""]
    elif entry_status == "Completed" and 'Addiction' in df_display.columns:
        df_display = df_display[df_display['Addiction'].astype(str).str.strip() != ""]

    st.dataframe(df_display, width="stretch", hide_index=True)

    csv_data = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Full Integrated List (CSV)", csv_data, "Adverse_Outcomes_Integrated.csv", "text/csv")
else:
    st.info("ℹ️ No records found in the New Sheet.")
