import streamlit as st
import pandas as pd
import base64
import os
import json
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

# The new dedicated Google Sheet for Adverse Outcomes & Field Entries
NEW_SHEET_URL = "https://docs.google.com/spreadsheets/d/11JHb7Zv4KqV_PAY9REGBVdkLwqBSubvgtSrr1ulGRzA/edit"
new_sheet = client.open_by_url(NEW_SHEET_URL).sheet1

# Get all previously submitted IDs to prevent duplicates (assumes Episode ID is in Column C / Index 3)
existing_records = new_sheet.get_all_records()
submitted_ids = [str(row.get('Episode ID', '')).strip().upper() for row in existing_records]

# 2. Fetch Master Patient Data (For Searching & Validation)
@st.cache_data(ttl=600, show_spinner="Loading Patient Master Data...")
def load_master_data():
    # The existing master sheet, converted to CSV output for Pandas
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSMyoouzVWkM5Xx6Ot0kcIyvKQfuVfDq6REJTARKAr2AnAUdey2TlOibBanMoognLKji4oV2g04T9A6/pub?output=csv"
    try:
        df = pd.read_csv(url, dtype=str)
        # Normalize headers just like your old code
        df.columns = df.columns.str.strip().str.upper()
        return df
    except:
        return pd.DataFrame()

df_master = load_master_data()

# ==========================================
# 📊 EXECUTIVE SUMMARY (MOH VIEW)
# ==========================================
st.markdown("""
<style>
    .kpi-card { background-color: #0f4a8a; color: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .kpi-title { font-size: 14px; text-transform: uppercase; font-weight: bold; opacity: 0.9; }
    .kpi-value { font-size: 32px; font-weight: 900; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='color: #0f4a8a; font-weight: 800;'>📊 Executive Summary</h3>", unsafe_allow_html=True)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

# Note: Placeholders until formula logic is added
with kpi1:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>Total Adverse Outcomes</div><div class='kpi-value'>142</div></div>", unsafe_allow_html=True)
with kpi2:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>Ahmedabad Residents</div><div class='kpi-value'>88%</div></div>", unsafe_allow_html=True)
with kpi3:
    st.markdown("<div class='kpi-card' style='background-color: #16a34a;'><div class='kpi-title'>Success Rate</div><div class='kpi-value'>TBD</div></div>", unsafe_allow_html=True)
with kpi4:
    st.markdown("<div class='kpi-card' style='background-color: #dc2626;'><div class='kpi-title'>Death Rate</div><div class='kpi-value'>TBD</div></div>", unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid #cbd5e1; margin: 30px 0;'>", unsafe_allow_html=True)

# ==========================================
# 📝 FIELD STAFF DATA ENTRY
# ==========================================
st.markdown("<h3 style='color: #0f4a8a; font-weight: 800;'>📝 Field Staff Data Entry</h3>", unsafe_allow_html=True)

search_id = st.text_input("🔍 Enter Patient Episode ID to Log Data", placeholder="e.g. 04-26-12345").strip().upper()

if st.button("Search Patient") or search_id:
    if not search_id:
        st.warning("Please enter an ID.")
        st.stop()
        
    # --- Check 1: One-Time Entry Only ---
    if search_id in submitted_ids:
        st.error(f"⛔ Data for Episode ID **{search_id}** has already been submitted. Duplicate entries are not allowed.")
        st.stop()

    # --- Find Patient in Master ---
    if not df_master.empty and 'EPISODE ID' in df_master.columns:
        patient_match = df_master[df_master['EPISODE ID'] == search_id]
        
        if patient_match.empty:
            st.error(f"⚠️ Patient ID **{search_id}** not found in the Master database.")
            st.stop()
            
        patient_data = patient_match.iloc[0]
        patient_tu = str(patient_data.get('TB UNIT', '')).strip().upper()
        patient_name = str(patient_data.get('PATIENT NAME', 'Unknown')).strip().title()

        # --- Check 2: TB Unit Access Restriction ---
        if st.session_state.role in ["TB_UNIT", "TU"]:
            staff_tu = st.session_state.target.strip().upper()
            if staff_tu not in patient_tu:
                st.error(f"⛔ Access Denied: Patient **{search_id}** belongs to {patient_tu}. You are only authorized to enter data for {staff_tu}.")
                st.stop()

        # --- Display Patient Info & Form ---
        st.success(f"✅ Patient Confirmed: **{patient_name}** | TB Unit: **{patient_tu}**")
        
        with st.form("adverse_entry_form", clear_on_submit=True):
            st.write("### Root Cause Analysis")
            col1, col2 = st.columns(2)
            with col1:
                addiction = st.selectbox("Does the patient have any addiction?", ["Select", "YES - Alcohol", "YES - Tobacco", "YES - Multiple", "NO"])
                comorbidity = st.selectbox("Known Comorbidities?", ["Select", "Diabetes", "HIV", "None", "Other"])
            with col2:
                migration = st.selectbox("Is the patient a migratory worker?", ["Select", "YES", "NO"])
                staff_notes = st.text_area("Additional Notes (Optional)")
                
            submit_btn = st.form_submit_button("💾 Submit to Database", use_container_width=True)
            
            if submit_btn:
                if "Select" in [addiction, comorbidity, migration]:
                    st.error("⚠️ Please select an answer for all dropdown questions.")
                else:
                    timestamp = datetime.now(india_tz).strftime("%d-%b-%Y %H:%M:%S")
                    
                    # Columns to append: [Timestamp, Submitted By, Episode ID, Patient Name, TB Unit, Addiction, Comorbidity, Migration, Notes]
                    new_row = [timestamp, st.session_state.current_user, search_id, patient_name, patient_tu, addiction, comorbidity, migration, staff_notes]
                    
                    try:
                        new_sheet.append_row(new_row)
                        st.success(f"🎉 Success! Data for {search_id} has been securely logged.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"❌ Failed to write to database: {e}")
    else:
        st.error("⚠️ Master database is empty or missing the 'EPISODE ID' column.")
