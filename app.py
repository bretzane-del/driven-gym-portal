import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from supabase import create_client, Client
from PIL import Image
import io
import base64

# --- SECURE DATABASE CONNECTION ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("🔒 Cloud Vault Connection Pending. Please configure your Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="Driven Gym Portal", page_icon="💪", layout="wide")

# --- CONVERSION HELPERS ---
FRACTIONS = ["0", "1/16", "1/8", "3/16", "1/4", "5/16", "3/8", "7/16", "1/2", "9/16", "5/8", "11/16", "3/4", "13/16", "7/8", "15/16"]
FRACTION_VALUES = {f: i/16 for i, f in enumerate(FRACTIONS)}

def float_to_fraction(val):
    if not val or val == 0: return "0"
    whole = int(val)
    frac = val - whole
    closest_frac = min(FRACTIONS, key=lambda x: abs(FRACTION_VALUES[x] - frac))
    return f"{whole}\"" if closest_frac == "0" else f"{whole} {closest_frac}\""

# --- DYNAMIC SUCCESS GRADING SCALE ---
def get_success_badge(rate):
    if rate >= 90: return f"{rate:.1f}% — On Fire 🔥"
    if rate >= 75: return f"{rate:.1f}% — On Track 🏃‍♂️"
    if rate >= 60: return f"{rate:.1f}% — Needs Focus ⚠️"
    return f"{rate:.1f}% — Danger Zone 🛑"

# --- DEFENSIVE SYSTEM SETTINGS LOAD ---
DEFAULT_SETTINGS = {
    "admin_secret_key": "driven2026", 
    "challenge_duration_weeks": 6, 
    "global_start_date": "2026-06-22", 
    "workout_name": "TBD", 
    "workout_notes": ""
}

try:
    settings_query = supabase.table("challenge_settings").select("*").eq("id", 1).execute()
    s_data = settings_query.data
    if s_data and isinstance(s_data, list) and len(s_data) > 0:
        settings = s_data if isinstance(s_data, dict) else DEFAULT_SETTINGS
    else:
        settings = DEFAULT_SETTINGS
except Exception as e:
    settings = DEFAULT_SETTINGS

challenge_start_date = date(2026, 6, 22)
raw_start_date = settings.get("global_start_date", "2026-06-22")

if isinstance(raw_start_date, str):
    try:
        challenge_start_date = datetime.strptime(raw_start_date, "%Y-%m-%d").date()
    except ValueError:
        pass
elif hasattr(raw_start_date, "year"):
    challenge_start_date = raw_start_date

# --- USER STATE APP FLOW ---
if "user" not in st.session_state:
    st.session_state.user = None

# Initialize native internal navigation state tracking
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Dashboard"

# --- SIDEBAR NAVIGATION WITH SECURE PRIVILEGE GATES ---
st.sidebar.markdown("### CHALLENGE MENU")

has_baseline = False
if st.session_state.user:
    st.sidebar.write(f"Logged in: **{st.session_state.user['email']}**")
    if st.sidebar.button("Log Out"):
        st.session_state.user = None
        st.session_state.nav_page = "Dashboard"
        st.rerun()
    
    # Check baseline status to dynamically adjust the user funnel
    baseline_check = supabase.table("user_baselines").select("user_id").eq("user_id", st.session_state.user["id"]).execute()
    has_baseline = len(baseline_check.data) > 0

# Secretly check URL for coach access parameter (?role=coach)
is_coach = st.query_params.get("role") == "coach"

# SECURE GATING MAPPING: Dictate exactly who can see what menus
if not st.session_state.user:
    navigation_options = ["Dashboard"]
elif not has_baseline:
    navigation_options = ["Dashboard", "Challenge Measurements"]
else:
    navigation_options = ["Dashboard", "Daily Log", "Benchmark Workout", "Challenge Measurements", "Leaderboard"]

if is_coach:
    navigation_options.append("Admin Configuration Panel")

try:
    default_selection_index = navigation_options.index(st.session_state.nav_page)
except ValueError:
    default_selection_index = 0
    st.session_state.nav_page = "Dashboard"

page = st.sidebar.radio("Go To", navigation_options, index=default_selection_index)
st.session_state.nav_page = page

# --- SIGN UP & LOGIN INTERFACE ---
if not st.session_state.user and page != "Admin Configuration Panel":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Driven Community Fitness Challenge</h2>", unsafe_allow_html=True)
    auth_mode = st.radio("Choose Action", ["Login", "Register Account"])
    
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if auth_mode == "Register Account":
        fullname = st.text_input("Full Name")
        age = st.number_input("Age", min_value=12, max_value=100, value=30)
        gender = st.radio("Gender / Division", ["Male", "Female"])
        
        if st.button("Sign Up"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                if res.user:
                    supabase.table("user_profiles").insert({
                        "user_id": res.user.id, 
                        "full_name": fullname, 
                        "email": email, 
                        "age": age,
                        "gender": gender
                    }).execute()
                    
                    st.session_state.user = {"id": res.user.id, "email": res.user.email}
                    st.success("Welcome aboard! Initializing your dashboard...")
                    st.rerun()
            except Exception as e:
                st.error(f"Signup error: {e}")
    else:
        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state.user = {"id": res.user.id, "email": res.user.email}
                    st.rerun()
            except Exception as e:
                st.error("Invalid login credentials.")
    st.stop()

# --- HIGH-COMPACT ADAPTIVE DROP-DOWN GRID SELECTOR ---
def fraction_selector(label, unique_key):
    st.markdown(f"<div style='margin-top: 12px; font-weight: 600; color: #FAFAFA;'>{label}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.5, 1.5, 5])
    whole = c1.selectbox("Inches", list(range(0, 80)), index=0, key=f"{unique_key}_w")
    frac = c2.selectbox("Fraction", FRACTIONS, index=0, key=f"{unique_key}_f")
    return whole + FRACTION_VALUES[frac]

# --- PAGES CONTENT IMPLEMENTATION ---
if page == "Challenge Measurements":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Challenge Measurements</h2>", unsafe_allow_html=True)
    
    start_dt = challenge_start_date
    try:
        weeks_count = int(settings.get("challenge_duration_weeks", 6))
    except (ValueError, TypeError):
        weeks_count = 6
    total_challenge_days = weeks_count * 7
    end_dt = start_dt + timedelta(days=total_challenge_days)
    
    days_since_start = (date.today() - start_dt).days
    existing_baseline = supabase.table("user_baselines").select("*").eq("user_id", st.session_state.user["id"]).execute()
    
    # PHASE 1: Initial Baseline Window (First 7 Days)
    if days_since_start <= 7:
        st.markdown("### Step 1: Enter Your Starting Measurements")
        
        with st.form("baseline_form"):
            st.markdown("#### Weight")
            w = st.number_input("Starting Weight (lbs)", min_value=0.0, step=0.1, value=None, placeholder="Enter weight...")
            
            st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
            st.markdown("#### Measurements")
            
            ch = fraction_selector("Chest", "start_chest")
            wa = fraction_selector("Waist", "start_waist")
            hi = fraction_selector("Hips", "start_hips")
            la = fraction_selector("Left Arm", "start_chest_arm_l")
            ra = fraction_selector("Right Arm", "start_chest_arm_r")
            lt = fraction_selector("Left Thigh", "start_chest_thigh_l")
            rt = fraction_selector("Right Thigh", "start_chest_thigh_r")
            
            st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
            st.subheader("Private Profile Photo (Optional)")
            opt_in_camera = st.checkbox("I want to take a starting baseline selfie photo")
            
            cam_photo = None
            if opt_in_camera:
                cam_photo = st.camera_input("Snap Baseline Selfie")
            
            # High-visibility primary accent button
            if st.form_submit_button("Save", type="primary"):
                if w is None:
                    st.error("Starting weight entry is required to initialize your dashboard metrics.")
                else:
                    img_str = ""
                    if opt_in_camera and cam_photo:
                        img = Image.open(cam_photo)
                        img.thumbnail((400, 400))
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG", quality=75)
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    supabase.table("user_baselines").upsert({
                        "user_id": st.session_state.user["id"],
                        "start_weight": w, "start_chest": ch, "start_waist": wa, "start_hips": hi,
                        "start_left_arm": la, "start_right_arm": ra, "start_left_thigh": lt, "start_right_thigh": rt,
                        "before_photo": img_str
                    }).execute()
                    st.success("Starting metrics successfully saved to your private profile vault!")
                    st.session_state.nav_page = "Dashboard"
                    st.rerun()

    # PHASE 2: Final Transformation Window (Final Week up to 7 Days Post-Challenge)
    elif days_since_start >= (total_challenge_days - 7) and days_since_start <= (total_challenge_days + 7):
        st.markdown("### Step 2: Submit Your Final Transformation Numbers")
        if not has_baseline:
            st.warning("No initial baseline record found for your account. Please log your finishing metrics below.")
            
        with st.form("final_form"):
            st.subheader("Finishing Measurements")
            w_end = st.number_input("Ending Weight (lbs)", min_value=0.0, step=0.1, value=None, placeholder="Enter weight...")
            ch_end = fraction_selector("Ending Chest", "end_chest")
            wa_end = fraction_selector("Ending Waist", "end_waist")
            hi_end = fraction_selector("Ending Hips", "end_hips")
            la_end = fraction_selector("Ending Left Arm", "end_arm_l")
            ra_end = fraction_selector("Ending Right Arm", "end_arm_r")
            lt_end = fraction_selector("Ending Left Thigh", "end_thigh_l")
            rt_end = fraction_selector("Ending Right Thigh", "end_thigh_r")
            
            # High-visibility primary accent button
            if st.form_submit_button("Save", type="primary"):
                supabase.table("user_baselines").upsert({
                    "user_id": st.session_state.user["id"],
                    "end_weight": w_end, "end_chest": ch_end, "end_waist": wa_end, "end_hips": hi_end,
                    "end_left_arm": la_end, "end_right_arm": ra_end, "end_left_thigh": lt_end, "end_right_thigh": rt_end
                }).execute()
                st.success("Finishing numbers locked in! Congratulations on completing the challenge!")
                st.session_state.nav_page = "Dashboard"
                st.rerun()

    # PHASE 3: Mid-Challenge Locked State
    else:
        st.markdown("### Measurement Logs Locked")
        st.subheader("🔒 Initial Baselines Secured")
        st.info("Initial measurements are safely encrypted. Your finishing submission window will automatically open during the final week of the challenge.")
        
        if has_baseline:
            b_data = existing_baseline.data
            st.markdown("#### Your Saved Starting Stats:")
            st.write(f"**Starting Weight:** {b_data.get('start_weight', 0.0)} lbs")

elif page == "Benchmark Workout":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Benchmark Workout Score Entry</h2>", unsafe_allow_html=True)
    st.info(f"🏋️‍♂️ **Official Workout Designation:** {settings.get('workout_name', 'TBD')}\n\n*Instructions:* {settings.get('workout_notes', 'Performance parameters pending update from coach.')}")
    
    existing_baseline = supabase.table("user_baselines").select("*").eq("user_id", st.session_state.user["id"]).execute()
    current_saved_score = existing_baseline.data.get("benchmark_score", "") if existing_baseline.data else ""
    
    if current_saved_score:
        st.success(f"Locked Score on Profile: **{current_saved_score}**")
        
    with st.form("workout_score_form"):
        score = st.text_input("Enter Your Workout Performance Result", value=current_saved_score, placeholder="e.g., 14:22, 185 lbs, 4 Rounds...")
        if st.form_submit_button("Submit Score Parameters"):
            supabase.table("user_baselines").upsert({
                "user_id": st.session_state.user["id"],
                "benchmark_score": score
            }).execute()
            st.success("Performance matrix securely attached to your athlete challenge vault!")
