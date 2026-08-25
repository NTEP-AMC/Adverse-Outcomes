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
    df_users['Password'] = df_users['Password'].astype(str).str.strip()
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
                user_match = df_users[(df_users['Username'] == uname) & (df_users['Password'] == pwd)]
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

# 1. Connect to Google Sheets via Service Account (For Writing Data)
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
    existing_records = new_sheet.get_all_records()
    submitted_ids = [str(row.get('Episode ID', '')).strip().upper() for row in existing_records if str(row.get('Episode ID', '')).strip()]
except Exception as e:
    new_sheet = None
    submitted_ids = []

# 2. Fetch Data from Master & This Week Tabs
BASE_OUTCOME_URL = "https://docs.google.com/spreadsheets/d/1Dfvl87uaZZ12_5F4dhHXTP_u8i9NM9TASWN8wyX18nE/export?format=csv&gid="

@st.cache_data(ttl=600, show_spinner="Fetching latest registers and calculating metrics...")
def load_all_registers():
    import urllib.request
    
    def get_sheet_df(gid):
        try:
            url = BASE_OUTCOME_URL + gid
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
                return pd.read_csv(io.BytesIO(content), low_memory=False, dtype=str, on_bad_lines='skip')
        except:
            return pd.DataFrame()

    df_m = get_sheet_df("1027512112") # MASTER tab
    df_t = get_sheet_df("1898426568") # THIS WEEK tab
    df_p = get_sheet_df("1981365704") # PREVIOUS WEEK tab

    return df_m, df_t, df_p

df_master_raw, df_this_raw, df_prev_raw = load_all_registers()

# ---------------------------------------------------------
# 🧮 CALCULATION ENGINE: SUCCESS RATE & DEATH RATE
# ---------------------------------------------------------
success_rate_str = "0%"
death_rate_str = "0%"

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
                if c_clean == p_clean:
                    return df[c]
        idx = cx(fallback_col_letter)
        if idx < len(df.columns):
            return df.iloc[:, idx]
        return pd.Series([""] * len(df))

    ep_series = get_col_series(df_this_raw, ['EPISODE ID', 'NTEP ID', 'ID'], 'M').fillna("").astype(str).str.strip()
    regimen_series = get_col_series(df_this_raw, ['TYPE OF TB REGIMEN', 'REGIMEN', 'TYPE_OF_TB_REGIMEN', 'REGIME'], 'BJ').fillna("").astype(str).str.upper()
    outcome_series = get_col_series(df_this_raw, ['TREATMENT OUTCOME', 'OUTCOME'], 'BK').fillna("").astype(str).str.upper().str.strip()

    valid_mask = ~ep_series.isin(["", "NAN", "NONE", "NULL", "N/A"])
    total_patients = valid_mask.sum()

    if total_patients > 0:
        regimen_mask = regimen_series.str.contains("2HRZE/4HRE|2HRZES|4HRE|2HRZE", regex=True, na=False)
        
        # Success Rate: Eligible Regimen AND Outcome in [TREATMENT_COMPLETE, CURED]
        success_mask = valid_mask & regimen_mask & outcome_series.str.contains("COMPLETE|CURED", regex=True, na=False)
        success_count = success_mask.sum()
        success_pct = (success_count / total_patients) * 100
        success_rate_str = f"{success_pct:.1f}%"

        # Death Rate: Eligible Regimen AND Outcome == DIED
        death_mask = valid_mask & regimen_mask & outcome_series.str.contains("DIED|DEATH", regex=True, na=False)
        death_count = death_mask.sum()
        death_pct = (death_count / total_patients) * 100
        death_rate_str = f"{death_pct:.1f}%"

# ---------------------------------------------------------
# ⚙️ MASTER DATA FORMATTING & MERGING
# ---------------------------------------------------------
df_combined_master = df_master_raw.copy()

if not df_combined_master.empty:
    rename_map = {}
    for col in df_combined_master.columns:
        c_clean = re.sub(r'[^A-Z0-9]', '', str(col).upper())
        if c_clean in ['AGE', 'PATIENTAGE']: rename_map[col] = 'Age'
        elif c_clean in ['REGIME', 'REGIMEN', 'TYPEOFTBREGIMEN']: rename_map[col] = 'Type_of_TB_regimen'
        elif c_clean in ['EPISODEID', 'NTEPID', 'ID', 'PATIENTID']: rename_map[col] = 'Episode ID'
        elif c_clean in ['TREATMENTOUTCOME', 'OUTCOME']: rename_map[col] = 'Treatment Outcome'
        elif c_clean in ['ZONE', 'CURRENTZONE', 'DISTRICT']: rename_map[col] = 'ZONE'
        elif c_clean in ['TBUNIT', 'TU']: rename_map[col] = 'TB Unit'
        elif c_clean in ['PHI', 'HEALTHFACILITY', 'FACILITY']: rename_map[col] = 'PHI'
        elif c_clean in ['PATIENTNAME', 'NAME']: rename_map[col] = 'Patient Name'
        elif c_clean in ['FACILITYTYPE', 'TYPE']: rename_map[col] = 'Facility Type'
        elif c_clean in ['ADVERSEDATE', 'DATE']: rename_map[col] = 'ADVERSE DATE'
        elif c_clean in ['DIAGNOSISDATE']: rename_map[col] = 'Diagnosis Date'
        elif c_clean in ['INITIATIONDATE']: rename_map[col] = 'Initiation Date'
        elif c_clean in ['OUTCOMEDATE']: rename_map[col] = 'Outcome Date'

    df_combined_master = df_combined_master.rename(columns=rename_map)

total_adverse_count = len(df_combined_master)

# Calculate Ahmedabad Residents %
ahmedabad_pct_str = "0%"
if total_adverse_count > 0 and 'ZONE' in df_combined_master.columns:
    ahmedabad_mask = df_combined_master['ZONE'].astype(str).str.upper().str.contains("AHMEDABAD|EAST|WEST|NORTH|SOUTH|CENTRAL|AMC", regex=True, na=False)
    ahmedabad_pct = (ahmedabad_mask.sum() / total_adverse_count) * 100
    ahmedabad_pct_str = f"{int(ahmedabad_pct)}%"

# Filter by role
if st.session_state.role in ["TB_UNIT", "TU"] and 'TB Unit' in df_combined_master.columns:
    staff_tu = st.session_state.target.strip().upper()
    df_combined_master = df_combined_master[df_combined_master['TB Unit'].astype(str).str.upper().str.contains(staff_tu, na=False)]
elif st.session_state.role == "ZONE" and 'ZONE' in df_combined_master.columns:
    staff_z = st.session_state.target.replace("ZONE", "").strip().upper()
    df_combined_master = df_combined_master[df_combined_master['ZONE'].astype(str).str.upper().str.contains(staff_z, na=False)]

# ==========================================
# 📊 EXECUTIVE SUMMARY (MOH VIEW)
# ==========================================
st.markdown("""
<style>
    .kpi-card { background-color: #0A3A6E; color: white; padding: 18px 10px; border-radius: 8px; text-align: center; }
    .kpi-title { font-size: 12px; text-transform: uppercase; font-weight: 700; opacity: 0.9; }
    .kpi-value { font-size: 28px; font-weight: 900; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>📊 Executive Summary</h3>", unsafe_allow_html=True)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Total Adverse Outcomes</div><div class='kpi-value'>{total_adverse_count}</div></div>", unsafe_allow_html=True)
with kpi2:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Ahmedabad Residents</div><div class='kpi-value'>{ahmedabad_pct_str}</div></div>", unsafe_allow_html=True)
with kpi3:
    st.markdown(f"<div class='kpi-card' style='background-color: #16a34a;'><div class='kpi-title'>Success Rate</div><div class='kpi-value'>{success_rate_str}</div></div>", unsafe_allow_html=True)
with kpi4:
    st.markdown(f"<div class='kpi-card' style='background-color: #dc2626;'><div class='kpi-title'>Death Rate</div><div class='kpi-value'>{death_rate_str}</div></div>", unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid #cbd5e1; margin: 25px 0;'>", unsafe_allow_html=True)

# ==========================================
# 📝 FIELD STAFF DATA ENTRY MODULE
# ==========================================
st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>📝 Field Staff Data Entry</h3>", unsafe_allow_html=True)

search_id = st.text_input("🔍 Enter Patient Episode ID to Log Data", placeholder="e.g. 04-26-12345").strip().upper()

if search_id:
    if search_id in submitted_ids:
        st.error(f"⛔ Data for Episode ID **{search_id}** has already been submitted. Duplicate entries are not allowed.")
    else:
        # Check in Master or This Week
        patient_match = pd.DataFrame()
        if not df_combined_master.empty and 'Episode ID' in df_combined_master.columns:
            patient_match = df_combined_master[df_combined_master['Episode ID'].astype(str).str.strip().str.upper() == search_id]

        if patient_match.empty:
            st.error(f"⚠️ Patient ID **{search_id}** not found in the current adverse list.")
        else:
            p_row = patient_match.iloc[0]
            p_name = str(p_row.get('Patient Name', 'Unknown')).strip().title()
            p_tu = str(p_row.get('TB Unit', 'Unknown')).strip().upper()
            p_out = str(p_row.get('Treatment Outcome', 'N/A')).strip().upper()

            # TB Unit authorization check
            if st.session_state.role in ["TB_UNIT", "TU"]:
                staff_tu = st.session_state.target.strip().upper()
                if staff_tu not in p_tu:
                    st.error(f"⛔ Access Denied: Patient belongs to TB Unit **{p_tu}**. You are only authorized for **{staff_tu}**.")
                    st.stop()

            st.success(f"✅ Patient: **{p_name}** | TB Unit: **{p_tu}** | Outcome: **{p_out}**")

            with st.form("field_entry_form", clear_on_submit=True):
                st.write("#### Patient Root Cause & Questionnaire")
                fc1, fc2 = st.columns(2)
                with fc1:
                    addiction = st.selectbox("Does the patient have any addiction?", ["Select", "YES - Alcohol", "YES - Tobacco", "YES - Multiple", "NO"])
                    comorbidity = st.selectbox("Known Comorbidities?", ["Select", "Diabetes", "HIV", "Hypertension", "None", "Other"])
                with fc2:
                    migration = st.selectbox("Is the patient a migratory resident?", ["Select", "YES - Native outside Ahmedabad", "NO - Local Resident"])
                    staff_notes = st.text_area("Field Staff Remarks / Cause Summary")

                submit_btn = st.form_submit_button("💾 Save to Google Sheet", use_container_width=True)

                if submit_btn:
                    if "Select" in [addiction, comorbidity, migration]:
                        st.error("⚠️ Please answer all dropdown questions before submitting.")
                    else:
                        timestamp = datetime.now(india_tz).strftime("%d-%b-%Y %H:%M:%S")
                        new_row = [timestamp, st.session_state.current_user, search_id, p_name, p_tu, addiction, comorbidity, migration, staff_notes]
                        
                        try:
                            if new_sheet:
                                new_sheet.append_row(new_row)
                                submitted_ids.append(search_id)
                                st.success(f"🎉 Successfully submitted data for Episode ID: {search_id}!")
                                st.balloons()
                            else:
                                st.error("❌ Google Sheet connection is not initialized.")
                        except Exception as e:
                            st.error(f"❌ Error writing to Google Sheet: {e}")

st.markdown("<hr style='border: 1px solid #cbd5e1; margin: 25px 0;'>", unsafe_allow_html=True)

# ==========================================
# 📋 MASTER ADVERSE OUTCOMES DATA TABLE
# ==========================================
st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>📋 Adverse Outcomes Line List</h3>", unsafe_allow_html=True)

if not df_combined_master.empty:
    f1, f2, f3 = st.columns(3)
    with f1:
        opts_out = sorted([x for x in df_combined_master['Treatment Outcome'].unique() if str(x).strip() != ""]) if 'Treatment Outcome' in df_combined_master.columns else []
        sel_out = st.multiselect("Filter by Treatment Outcome", opts_out, default=opts_out)
    with f2:
        opts_zone = sorted([x for x in df_combined_master['ZONE'].unique() if str(x).strip() != ""]) if 'ZONE' in df_combined_master.columns else []
        sel_zone = st.multiselect("Filter by Zone", opts_zone)
    with f3:
        opts_per = sorted([x for x in df_combined_master['ADVERSE DATE'].unique() if str(x).strip() != ""]) if 'ADVERSE DATE' in df_combined_master.columns else []
        sel_per = st.multiselect("Filter by Adverse Date Tag", opts_per)

    df_display = df_combined_master.copy()
    if sel_out and 'Treatment Outcome' in df_display.columns: df_display = df_display[df_display['Treatment Outcome'].isin(sel_out)]
    if sel_zone and 'ZONE' in df_display.columns: df_display = df_display[df_display['ZONE'].isin(sel_zone)]
    if sel_per and 'ADVERSE DATE' in df_display.columns: df_display = df_display[df_display['ADVERSE DATE'].isin(sel_per)]

    master_cols = ['ADVERSE DATE', 'ZONE', 'TB Unit', 'PHI', 'Facility Type', 'Patient Name', 'Episode ID', 'Age', 'Type_of_TB_regimen', 'Diagnosis Date', 'Initiation Date', 'Outcome Date', 'Treatment Outcome', 'On Treatment Days']
    cols_to_show = [c for c in master_cols if c in df_display.columns]
    
    st.dataframe(df_display[cols_to_show] if cols_to_show else df_display, width="stretch", hide_index=True)

    csv_data = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Filtered Master List (CSV)", csv_data, "Adverse_Outcomes_Filtered.csv", "text/csv")
else:
    st.info("ℹ️ No records found in the Master Register.")
