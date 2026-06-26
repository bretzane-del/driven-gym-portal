start_dt = challenge_start_date
try:
    weeks_count = int(settings.get("challenge_duration_weeks", 6))
except (ValueError, TypeError):
    weeks_count = 6
total_challenge_days = weeks_count * 7
end_dt = start_dt + timedelta(days=total_challenge_days)
days_since_start = (date.today() - start_dt).days

try:
    existing_baseline_query = supabase.table("user_baselines").select("*").eq("user_id", st.session_state.user["id"]).execute()
    b_data = safe_extract(existing_baseline_query.data)
except Exception:
    b_data = {}

if days_since_start <= 7:
    st.markdown("### Step 1: Enter Your Starting Measurements")
    if has_baseline:
        st.info("✏️ **Revision Mode Active:** Your currently saved measurements are pre-populated below. You can modify any field and save changes until your initial challenge week expires.")
        current_weight = b_data.get("start_weight")
    else:
        current_weight = None
    
    with st.form("baseline_form"):
        st.markdown("#### Weight")
        w = st.number_input("Starting Weight (lbs)", min_value=0.0, step=0.1, value=current_weight, placeholder="Enter weight...")
        
        st.markdown("---")
        st.markdown("#### Measurements")
        
        ch = fraction_selector("Chest", "start_chest", b_data.get("start_chest", 0.0))
        wa = fraction_selector("Waist", "start_waist", b_data.get("start_waist", 0.0))
        hi = fraction_selector("Hips", "start_hips", b_data.get("start_hips", 0.0))
        la = fraction_selector("Left Arm", "start_chest_arm_l", b_data.get("start_left_arm", 0.0))
        ra = fraction_selector("Right Arm", "start_chest_arm_r", b_data.get("start_right_arm", 0.0))
        lt = fraction_selector("Left Thigh", "start_chest_thigh_l", b_data.get("start_left_thigh", 0.0))
        rt = fraction_selector("Right Thigh", "start_chest_thigh_r", b_data.get("start_right_thigh", 0.0))
        
        st.markdown("---")
        st.subheader("Private Profile Photo (Optional)")
        uploaded_photo = st.file_uploader("Snap or select a baseline photo", type=["jpg", "jpeg", "png"])
        
        if st.form_submit_button("Save", type="primary"):
            if w is None:
                st.error("Starting weight entry is required to save your metrics.")
            else:
                img_str = b_data.get("before_photo", "")
                if uploaded_photo is not None:
                    try:
                        img = Image.open(uploaded_photo)
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        img.thumbnail((400, 400))
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG", quality=75)
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                    except Exception:
                        pass
                
                try:
                    supabase.table("user_baselines").upsert({
                        "user_id": st.session_state.user["id"],
                        "start_weight": w, "start_chest": ch, "start_waist": wa, "start_hips": hi,
                        "start_left_arm": la, "start_right_arm": ra, "start_left_thigh": lt, "start_right_thigh": rt,
                        "before_photo": img_str
                    }).execute()
                    st.success("Measurements recorded successfully!")
                    st.session_state.nav_page = "Dashboard"
                    st.rerun()
                except Exception as db_err:
                    st.error(f"Database error: {db_err}")

elif days_since_start >= (total_challenge_days - 7) and days_since_start <= (total_challenge_days + 7):
    st.markdown("### Step 2: Submit Your Final Transformation Numbers")
    with st.form("final_form"):
        st.subheader("Finishing Measurements")
        w_end = st.number_input("Ending Weight (lbs)", min_value=0.0, step=0.1, value=b_data.get("end_weight"), placeholder="Enter weight...")
        ch_end = fraction_selector("Ending Chest", "end_chest", b_data.get("end_chest", 0.0))
        wa_end = fraction_selector("Ending Waist", "end_waist", b_data.get("end_waist", 0.0))
        hi_end = fraction_selector("Ending Hips", "end_hips", b_data.get("end_hips", 0.0))
        la_end = fraction_selector("Ending Left Arm", "end_arm_l", b_data.get("end_left_arm", 0.0))
        ra_end = fraction_selector("Ending Right Arm", "end_arm_r", b_data.get("end_right_arm", 0.0))
        lt_end = fraction_selector("Ending Left Thigh", "end_thigh_l", b_data.get("end_left_thigh", 0.0))
        rt_end = fraction_selector("Ending Right Thigh", "end_thigh_r", b_data.get("end_right_thigh", 0.0))
        
        if st.form_submit_button("Save", type="primary"):
            try:
                supabase.table("user_baselines").upsert({
                    "user_id": st.session_state.user["id"],
      
