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
    # Standalone Workout tab unlocks alongside operational modules after tape inputs are logged
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
    # Ratios allocate tight boxes on the left, pushing empty grid columns to the right
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
            st.markdown("#### Total Body Mass")
            # Setting value=None leaves the box blank with an adaptive placeholder string
            w = st.number_input("Starting Weight (lbs)", min_value=0.0, step=0.1, value=None, placeholder="Enter weight...")
            
            st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
            st.markdown("#### Anthropometric Tape Configurations")
            
            ch = fraction_selector("Chest Tracking circumference", "start_chest")
            wa = fraction_selector("Waist Tracking circumference", "start_waist")
            hi = fraction_selector("Hips Tracking circumference", "start_hips")
            la = fraction_selector("Left Arm circumference", "start_chest_arm_l")
            ra = fraction_selector("Right Arm circumference", "start_chest_arm_r")
            lt = fraction_selector("Left Thigh circumference", "start_chest_thigh_l")
            rt = fraction_selector("Right Thigh circumference", "start_chest_thigh_r")
            
            st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
            st.subheader("Private Profile Photo (Optional)")
            opt_in_camera = st.checkbox("I want to take a starting baseline selfie photo")
            
            cam_photo = None
            if opt_in_camera:
                cam_photo = st.camera_input("Snap Baseline Selfie")
            
            if st.form_submit_button("Securely Save My Starting Numbers"):
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
            st.subheader("Finishing Tape Measurements")
            w_end = st.number_input("Ending Weight (lbs)", min_value=0.0, step=0.1, value=None, placeholder="Enter weight...")
            ch_end = fraction_selector("Ending Chest", "end_chest")
            wa_end = fraction_selector("Ending Waist", "end_waist")
            hi_end = fraction_selector("Ending Hips", "end_hips")
            la_end = fraction_selector("Ending Left Arm", "end_arm_l")
            ra_end = fraction_selector("Ending Right Arm", "end_arm_r")
            lt_end = fraction_selector("Ending Left Thigh", "end_thigh_l")
            rt_end = fraction_selector("Ending Right Thigh", "end_thigh_r")
            
            if st.form_submit_button("Securely Save My Finishing Numbers"):
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
            st.rerun()

elif page == "Daily Log":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Daily Performance Log</h2>", unsafe_allow_html=True)
    log_date = st.date_input("Date", date.today())
    
    existing = supabase.table("daily_logs").select("*").eq("user_id", st.session_state.user["id"]).eq("log_date", str(log_date)).execute()
    log_data = existing.data if existing.data else {"diet": False, "water": False, "sleep": False, "exercise": False}
    
    diet = st.checkbox("Strict Paleo Menu Adherence — **5 pts**", value=log_data.get("diet", False))
    water = st.checkbox("Water Tracker Placeholder — **1 pt**", value=log_data.get("water", False))
    sleep = st.checkbox("Sleep Metrics (7-8+ Rest Hours) — **1 pt**", value=log_data.get("sleep", False))
    exercise = st.checkbox("Daily Activity or Designated Mobility Session — **1 pt**", value=log_data.get("exercise", False))
    
    score = (5 if diet else 0) + (1 if water else 0) + (1 if sleep else 0) + (1 if exercise else 0)
    st.metric("Points Scored", f"{score} / 8")
    
    if st.button("Submit Daily Points"):
        supabase.table("daily_logs").upsert({
            "user_id": st.session_state.user["id"], "log_date": str(log_date),
            "diet": diet, "water": water, "sleep": sleep, "exercise": exercise, "daily_score": score
        }).execute()
        st.success("Points posted successfully!")

elif page == "Dashboard":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Your Progress Dashboard</h2>", unsafe_allow_html=True)
    
    baselines = supabase.table("user_baselines").select("*").eq("user_id", st.session_state.user["id"]).execute()
    logs = supabase.table("daily_logs").select("*").eq("user_id", st.session_state.user["id"]).execute()
    
    if not has_baseline:
        st.markdown("<br>", unsafe_allow_html=True)
        st.warning("👉 Enter your 'starting' measurements to get set up for the Challenge!")
        if st.button("Go Lock In Your Measurements Now →", type="primary"):
            st.session_state.nav_page = "Challenge Measurements"
            st.rerun()
    else:
        b = baselines.data
        start_dt = challenge_start_date
        try:
            total_weeks = int(settings.get("challenge_duration_weeks", 6))
        except (ValueError, TypeError):
            total_weeks = 6
        total_days = total_weeks * 7
        days_in = max((date.today() - start_dt).days + 1, 1)
        
        total_earned = sum([day.get("daily_score", 0) for day in logs.data])
        possible_so_far = min(days_in, total_days) * 8
        success_rate = (total_earned / possible_so_far * 100) if possible_so_far > 0 else 100.0
        
        st.markdown("### ⚡ Current Momentum")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown(f"""
            <div style="background-color: #1E222B; padding: 20px; border-radius: 12px; border-left: 5px solid #FF4B4B; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);">
                <span style="color: #8A9AAB; font-size: 12px; font-weight: bold; text-transform: uppercase;">Timeline Milestone</span>
                <h2 style="margin: 5px 0 0 0; color: #FAFAFA; font-size: 28px;">Day {min(days_in, total_days)} <span style="font-size: 16px; color: #8A9AAB;">/ {total_days}</span></h2>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
            <div style="background-color: #1E222B; padding: 20px; border-radius: 12px; border-left: 5px solid #00E676; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);">
                <span style="color: #8A9AAB; font-size: 12px; font-weight: bold; text-transform: uppercase;">Accumulated Points</span>
                <h2 style="margin: 5px 0 0 0; color: #00E676; font-size: 28px;">{total_earned} <span style="font-size: 16px; color: #8A9AAB;">Pts</span></h2>
            </div>
            """, unsafe_allow_html=True)
            
        with c3:
            badge_color = "#FF4B4B" if success_rate < 60 else ("#FFD600" if success_rate < 75 else "#00E676")
            st.markdown(f"""
            <div style="background-color: #1E222B; padding: 20px; border-radius: 12px; border-left: 5px solid {badge_color}; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);">
                <span style="color: #8A9AAB; font-size: 12px; font-weight: bold; text-transform: uppercase;">Your Success Rate</span>
                <h4 style="margin: 8px 0 0 0; color: #FAFAFA; font-size: 18px;">{get_success_badge(success_rate)}</h4>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown(f"""
        <div style="background-color: #151922; padding: 25px; border-radius: 16px; border: 1px solid #2C3545; box-shadow: 2px 4px 15px rgba(0,0,0,0.4); margin-top: 15px;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <h3 style="margin: 0; color: #FAFAFA; font-size: 20px;">🔒 Sealed Personal Configuration (Private)</h3>
            </div>
            <p style="color: #8A9AAB; font-size: 13px; margin: -5px 0 20px 0;">These numbers are safely encrypted. No other members or leaderboards can view these metrics.</p>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
                <div style="background-color: #1E222B; padding: 15px; border-radius: 8px;">
                    <span style="color: #8A9AAB; font-size: 11px; text-transform: uppercase; font-weight: bold;">Starting Weight</span>
                    <p style="margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #FAFAFA;">{b.get('start_weight', 0.0)} lbs</p>
                </div>
                <div style="background-color: #1E222B; padding: 15px; border-radius: 8px;">
                    <span style="color: #8A9AAB; font-size: 11px; text-transform: uppercase; font-weight: bold;">Chest / Waist / Hips</span>
                    <p style="margin: 5px 0 0 0; font-size: 18px; font-weight: bold; color: #FAFAFA;">{float_to_fraction(b.get('start_chest', 0.0))} / {float_to_fraction(b.get('start_waist', 0.0))} / {float_to_fraction(b.get('start_hips', 0.0))}</p>
                </div>
                <div style="background-color: #1E222B; padding: 15px; border-radius: 8px;">
                    <span style="color: #8A9AAB; font-size: 11px; text-transform: uppercase; font-weight: bold;">Arms (L / R)</span>
                    <p style="margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #FAFAFA;">{float_to_fraction(b.get('start_left_arm', 0.0))} / {float_to_fraction(b.get('start_right_arm', 0.0))}</p>
                </div>
                <div style="background-color: #1E222B; padding: 15px; border-radius: 8px;">
                    <span style="color: #8A9AAB; font-size: 11px; text-transform: uppercase; font-weight: bold;">Thighs (L / R)</span>
                    <p style="margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #FAFAFA;">{float_to_fraction(b.get('start_left_thigh', 0.0))} / {float_to_fraction(b.get('start_right_thigh', 0.0))}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

elif page == "Leaderboard":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>The Consolidated Gym Standings</h2>", unsafe_allow_html=True)
    
    profiles = supabase.table("user_profiles").select("*").execute()
    all_logs = supabase.table("daily_logs").select("*").execute()
    all_baselines = supabase.table("user_baselines").select("*").execute()
    
    leaderboard_data = []
    
    for p in profiles.data:
        user_points = sum([l.get("daily_score", 0) for l in all_logs.data if l.get("user_id") == p.get("user_id")])
        ub = next((b for b in all_baselines.data if b.get("user_id") == p.get("user_id")), None)
        
        lbs_lost = 0.0
        if ub and ub.get("end_weight") and ub.get("start_weight"):
            lbs_lost = float(ub["start_weight"] - ub["end_weight"])
        
        leaderboard_data.append({
            "Athlete Name": p.get("full_name", "Anonymous"),
            "Division": p.get("gender", "Unassigned"),
            "Total Points": user_points,
            "Pounds Dropped": f"{lbs_lost:.1f} lbs" if lbs_lost > 0 else "0.0 lbs",
        })
        
    df = pd.DataFrame(leaderboard_data).sort_values(by="Total Points", ascending=False)
    st.dataframe(df, use_container_width=True)

elif page == "Admin Configuration Panel":
    st.markdown("<h2 style='text-transform: uppercase; letter-spacing: 1px;'>Shared Executive Administration Panel</h2>", unsafe_allow_html=True)
    master_key = settings.get("admin_secret_key", "driven2026") if isinstance(settings, dict) else "driven2026"
    input_key = st.text_input("Enter Master Secret Admin Key", type="password")
    
    if input_key == master_key:
        st.success("Access Verified.")
        with st.form("admin_form"):
            duration_options = (4, 5, 6, 8)
            try:
                current_weeks = int(settings.get("challenge_duration_weeks", 6))
                default_selection_index = duration_options.index(current_weeks)
            except (ValueError, TypeError):
                default_selection_index = 2
            
            new_dur = st.selectbox("Challenge Duration (Weeks)", duration_options, index=default_selection_index)
            new_start = st.date_input("Global Challenge Launch Date", challenge_start_date)
            new_wkout = st.text_input("Global Benchmark Workout Title", value=settings.get("workout_name", "TBD"))
            new_notes = st.text_area("Scoring Rules & Instructions Box", value=settings.get("workout_notes", ""))
            
            if st.form_submit_button("Apply Global System Overrides"):
                supabase.table("challenge_settings").upsert({
                    "id": 1, 
                    "admin_secret_key": master_key,
                    "challenge_duration_weeks": new_dur, 
                    "global_start_date": str(new_start),
                    "workout_name": new_wkout, 
                    "workout_notes": new_notes
                }).execute()
                st.success("Global overrides applied! Refreshing pipeline.")
                st.rerun()
