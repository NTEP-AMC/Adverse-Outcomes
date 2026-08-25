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
    st.error("Could not connect to the New Google Sheet. Check credentials.")
    st.stop()
@st.cache_data(ttl=10, show_spinner="Syncing Live Data Tracker...")
def get_live_tracker():
    try:
        return pd.DataFrame(new_sheet.get_all_records())
    except:
        return pd.DataFrame()
df_live = get_live_tracker()
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

total_adverse_count = len(df_live)

# ---------------------------------------------------------
# 🧮 AHMEDABAD RESIDENT COUNT (used by KPI + breakdown card)
# ---------------------------------------------------------
ahmedabad_count = 0
ahmedabad_pct_str = "0%"
if total_adverse_count > 0 and 'ZONE' in df_live.columns:
    ahmedabad_mask = df_live['ZONE'].astype(str).str.upper().str.contains("AHMEDABAD|EAST|WEST|NORTH|SOUTH|CENTRAL|AMC", regex=True, na=False)
    ahmedabad_count = int(ahmedabad_mask.sum())
    ahmedabad_pct_str = f"{int((ahmedabad_count / total_adverse_count) * 100)}%"

# ---------------------------------------------------------
# 🧮 BIFURCATED BREAKDOWNS: Addiction / Comorbidity / Migration
# (built from the same Addiction/Comorbidity/Migration columns
#  captured by the data-entry editor below)
# ---------------------------------------------------------
addiction_breakdown = {}
comorbidity_breakdown = {}
migration_breakdown = {}
entry_completed_count = 0

if not df_live.empty:
    if 'Addiction' in df_live.columns:
        addic_series = df_live['Addiction'].fillna("").astype(str)
        entry_completed_count = int((addic_series.str.strip() != "").sum())
        addiction_breakdown = {
            "Alcohol":  int(addic_series.str.contains("Alcohol", case=False, na=False).sum()),
            "Tobacco":  int(addic_series.str.contains("Tobacco", case=False, na=False).sum()),
            "Multiple": int(addic_series.str.contains("Multiple", case=False, na=False).sum()),
            "None":     int(addic_series.str.contains(r"^NO(\s|-|$)", case=False, na=False, regex=True).sum()),
        }
    if 'Comorbidity' in df_live.columns:
        comorb_series = df_live['Comorbidity'].fillna("").astype(str)
        comorbidity_breakdown = {
            "Diabetes":     int(comorb_series.str.contains("Diabetes", case=False, na=False).sum()),
            "HIV":          int(comorb_series.str.contains("HIV", case=False, na=False).sum()),
            "Hypertension": int(comorb_series.str.contains("Hypertension", case=False, na=False).sum()),
            "Other":        int(comorb_series.str.contains("Other", case=False, na=False).sum()),
            "None":         int(comorb_series.str.contains(r"^None$", case=False, na=False, regex=True).sum()),
        }
    if 'Migration' in df_live.columns:
        mig_series = df_live['Migration'].fillna("").astype(str)
        migration_breakdown = {
            "Migrant (Outside Ahmedabad)": int(mig_series.str.contains("Native outside", case=False, na=False).sum()),
            "Local Resident":              int(mig_series.str.contains("Local Resident", case=False, na=False).sum()),
        }

# ==========================================
# 📊 EXECUTIVE SUMMARY (MOH VIEW) — REDESIGNED
# ==========================================
st.markdown("""
<style>
    /* ---- Primary KPI cards: flat, white, accent-bordered ---- */
    .kpi-card-v2 {
        background: #ffffff;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04);
        border-left: 5px solid #0A3A6E;
        height: 100%;
    }
    .kpi-icon-v2 { font-size: 20px; opacity: 0.85; }
    .kpi-label-v2 {
        font-size: 11px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.4px; color: #64748b; margin-top: 8px;
    }
    .kpi-number-v2 { font-size: 30px; font-weight: 800; color: #0f172a; margin-top: 2px; line-height: 1.1; }
    .kpi-sub-v2 { font-size: 11.5px; color: #64748b; margin-top: 8px; font-weight: 600; }
    .kpi-years-v2 { font-size: 10px; color: #94a3b8; margin-top: 4px; font-weight: 500; }

    /* ---- Secondary breakdown cards ---- */
    .breakdown-card {
        background: #f8fafc;
        border-radius: 10px;
        padding: 14px 16px 16px 16px;
        border: 1px solid #e2e8f0;
        height: 100%;
    }
    .breakdown-title { font-size: 12.5px; font-weight: 700; color: #334155; margin-bottom: 10px; }
    .breakdown-row { display: flex; justify-content: space-between; font-size: 12px; color: #475569; margin-top: 8px; }
    .breakdown-row b { color: #0f172a; }
    .progress-bg { background: #e2e8f0; border-radius: 4px; height: 6px; margin-top: 4px; overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 4px; }
    .breakdown-empty { font-size: 12px; color: #94a3b8; font-style: italic; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>📊 Executive Summary</h3>", unsafe_allow_html=True)

def render_kpi_card(icon, label, value, sub="", years="", accent="#0A3A6E"):
    sub_html = f"<div class='kpi-sub-v2'>{sub}</div>" if sub else ""
    years_html = f"<div class='kpi-years-v2'>{years}</div>" if years else ""
    return f"""
    <div class="kpi-card-v2" style="border-left-color:{accent};">
        <div class="kpi-icon-v2">{icon}</div>
        <div class="kpi-label-v2">{label}</div>
        <div class="kpi-number-v2">{value}</div>
        {sub_html}
        {years_html}
    </div>
    """

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
with kpi1:
    st.markdown(render_kpi_card("🧾", "Total Adverse Outcomes", total_adverse_count,
                                 sub=f"{entry_completed_count} of {total_adverse_count} entries completed",
                                 accent="#0A3A6E"), unsafe_allow_html=True)
with kpi2:
    st.markdown(render_kpi_card("🏙️", "Ahmedabad Residents", ahmedabad_pct_str,
                                 sub=f"{ahmedabad_count} of {total_adverse_count} records",
                                 accent="#2563eb"), unsafe_allow_html=True)
with kpi3:
    st.markdown(render_kpi_card("✅", "Success Rate", success_overall_str,
                                 sub="Among eligible regimens", years=success_years_str,
                                 accent="#16a34a"), unsafe_allow_html=True)
with kpi4:
    st.markdown(render_kpi_card("⚠️", "Initial Death Rate", init_death_overall_str,
                                 sub="Died before treatment initiation", years=init_death_years_str,
                                 accent="#f97316"), unsafe_allow_html=True)
with kpi5:
    st.markdown(render_kpi_card("⚰️", "Normal Death Rate", death_overall_str,
                                 sub="During treatment", years=death_years_str,
                                 accent="#dc2626"), unsafe_allow_html=True)

# ---------------------------------------------------------
# 🔍 DETAILED BIFURCATION (Addiction / Comorbidity / Migration)
# ---------------------------------------------------------
st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
st.markdown("<h4 style='color: #334155; font-weight: 700; font-size:16px;'>🔍 Detailed Breakdown of Adverse Outcomes</h4>", unsafe_allow_html=True)

def render_breakdown_card(title, icon, data_dict, total, accent):
    if total > 0 and data_dict:
        rows_html = ""
        for label, count in data_dict.items():
            pct = (count / total * 100) if total > 0 else 0
            rows_html += f"""
            <div class="breakdown-row">
                <span>{label}</span>
                <span><b>{count}</b>&nbsp;({pct:.0f}%)</span>
            </div>
            <div class="progress-bg"><div class="progress-fill" style="width:{pct:.0f}%; background:{accent};"></div></div>
            """
    else:
        rows_html = "<div class='breakdown-empty'>No entries recorded yet</div>"
    return f"""
    <div class="breakdown-card">
        <div class="breakdown-title">{icon} {title} &nbsp;<span style='color:#94a3b8; font-weight:500;'>(out of {total})</span></div>
        {rows_html}
    </div>
    """

b1, b2, b3 = st.columns(3)
with b1:
    st.markdown(render_breakdown_card("Addiction Status", "🍷", addiction_breakdown, total_adverse_count, accent="#7c3aed"), unsafe_allow_html=True)
with b2:
    st.markdown(render_breakdown_card("Comorbidity", "🏥", comorbidity_breakdown, total_adverse_count, accent="#0891b2"), unsafe_allow_html=True)
with b3:
    st.markdown(render_breakdown_card("Migration Status", "🧭", migration_breakdown, total_adverse_count, accent="#ca8a04"), unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid #cbd5e1; margin: 25px 0;'>", unsafe_allow_html=True)
# ==========================================
# 📝 INLINE SPREADSHEET EDITOR (DIRECT DATA ENTRY)
# ==========================================
st.markdown("<h3 style='color: #0A3A6E; font-weight: 800;'>📝 Interactive Line List & Field Data Entry</h3>", unsafe_allow_html=True)
st.markdown("<div style='font-size: 14px; margin-bottom:15px; color:#555;'>Double-click the cells in the <b>Addiction, Comorbidity, Migration, or Remarks</b> columns to edit them directly. Hit the Save button when you are done!</div>", unsafe_allow_html=True)
if not df_live.empty:
    df_display = df_live.copy()
    
    # Check if the setup is correct
    required_cols = ['Addiction', 'Comorbidity', 'Migration', 'Remarks']
    if not all(col in df_display.columns for col in required_cols):
        st.error(f"⚠️ Setup Required: Please ensure your Google Sheet has exactly these columns: {', '.join(required_cols)}")
        st.stop()
    
    # Ensure no NaN values for clean text editing
    for col in required_cols:
        df_display[col] = df_display[col].fillna("").astype(str)
    # 1. Role-Based Filtering
    if st.session_state.role in ["TB_UNIT", "TU"]:
        df_display = df_display[df_display['TB Unit'].astype(str).str.upper().str.contains(st.session_state.target.strip().upper(), na=False)]
    elif st.session_state.role == "ZONE":
        df_display = df_display[df_display['ZONE'].astype(str).str.upper().str.contains(st.session_state.target.replace("ZONE", "").strip().upper(), na=False)]
    # 2. Top Bar Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        opts_out = sorted([x for x in df_display['Treatment Outcome'].unique() if str(x).strip() != ""]) if 'Treatment Outcome' in df_display.columns else []
        sel_out = st.multiselect("Filter by Treatment Outcome", opts_out)
    with f2:
        opts_zone = sorted([x for x in df_display['ZONE'].unique() if str(x).strip() != ""]) if 'ZONE' in df_display.columns else []
        sel_zone = st.multiselect("Filter by Zone", opts_zone)
    with f3:
        entry_status = st.selectbox("Data Entry Status", ["All", "Pending Entry", "Completed"])
    if sel_out and 'Treatment Outcome' in df_display.columns: df_display = df_display[df_display['Treatment Outcome'].isin(sel_out)]
    if sel_zone and 'ZONE' in df_display.columns: df_display = df_display[df_display['ZONE'].isin(sel_zone)]
    
    if entry_status == "Pending Entry":
        df_display = df_display[df_display['Addiction'].str.strip() == ""]
    elif entry_status == "Completed":
        df_display = df_display[df_display['Addiction'].str.strip() != ""]
    # 🚨 CRITICAL: We must reset the index so Streamlit's editor maps perfectly to our filtered dataframe
    df_display = df_display.reset_index(drop=True)
    # 3. Configure the Interactive Table
    # Lock all historical columns to prevent accidental edits
    locked_cols = [col for col in df_display.columns if col not in required_cols]
    # Map the dropdown options directly into the table
    column_configuration = {
        "Addiction": st.column_config.SelectboxColumn("Addiction", options=["", "YES - Alcohol", "YES - Tobacco", "YES - Multiple", "NO"]),
        "Comorbidity": st.column_config.SelectboxColumn("Comorbidity", options=["", "Diabetes", "HIV", "Hypertension", "None", "Other"]),
        "Migration": st.column_config.SelectboxColumn("Migration", options=["", "YES - Native outside Ahmedabad", "NO - Local Resident"]),
        "Remarks": st.column_config.TextColumn("Remarks")
    }
    # Render the interactive Data Editor
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        disabled=locked_cols,
        column_config=column_configuration,
        key="master_data_editor"
    )
    # 4. Save Changes Engine (Pushes delta directly back to Google Sheets)
    if "master_data_editor" in st.session_state and st.session_state["master_data_editor"]["edited_rows"]:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save All Changes to Master Database", type="primary", use_container_width=True):
            with st.spinner("Writing updates securely to Google Sheets..."):
                edited_rows_dict = st.session_state["master_data_editor"]["edited_rows"]
                
                for row_idx, changes in edited_rows_dict.items():
                    # Map the edited row index back to the exact Episode ID
                    ep_id = df_display.iloc[int(row_idx)]['Episode ID']
                    
                    try:
                        # Assuming Episode ID is in Column H (Index 8)
                        cell = new_sheet.find(str(ep_id), in_column=8)
                        
                        # Get existing values, overwrite with any new changes made by the user
                        current_row = df_display.iloc[int(row_idx)]
                        addic_val = changes.get("Addiction", current_row.get("Addiction", ""))
                        comorb_val = changes.get("Comorbidity", current_row.get("Comorbidity", ""))
                        mig_val = changes.get("Migration", current_row.get("Migration", ""))
                        rem_val = changes.get("Remarks", current_row.get("Remarks", ""))
                        
                        timestamp = datetime.now(india_tz).strftime("%d-%b-%Y %H:%M:%S")
                        submitted_by = st.session_state.current_user
                        
                        # Target columns Q, R, S, T, U, V
                        cells_to_update = new_sheet.range(f'Q{cell.row}:V{cell.row}')
                        new_vals = [addic_val, comorb_val, mig_val, rem_val, submitted_by, timestamp]
                        
                        for i, val in enumerate(new_vals):
                            cells_to_update[i].value = str(val) if val is not None else ""
                        
                        new_sheet.update_cells(cells_to_update)
                        
                    except Exception as e:
                        st.error(f"❌ Failed to update Episode ID {ep_id}. Ensure the ID exists in Column H. Error: {e}")
                
                st.success("✅ All field data successfully saved to the Master Sheet!")
                get_live_tracker.clear() # Clears cache to fetch fresh data
                st.rerun()
else:
    st.info("ℹ️ No records found in the New Sheet.")
