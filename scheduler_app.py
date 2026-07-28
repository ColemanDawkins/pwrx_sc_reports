import calendar
import datetime as dt

import requests
import streamlit as st

st.set_page_config(
    page_title="PWRX Re-Test Scheduler",
    page_icon="📅",
    layout="wide",
)

API_URL = "https://web-production-4f00a.up.railway.app"

st.markdown(
    "<div style='text-align:center;padding:12px 0 8px;'>"
    "<h2 style='margin-bottom:0;'>📅 PWRX Re-Test Scheduler</h2>"
    "</div>"
    "<h4 style='text-align:center;color:#8a8a8a;margin-top:4px;margin-bottom:0;'>"
    "Book athlete re-test appointments</h4>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Session state ────────────────────────────────────────────────────────────
today = dt.date.today()
if "cal_year"       not in st.session_state: st.session_state.cal_year       = today.year
if "cal_month"      not in st.session_state: st.session_state.cal_month      = today.month
if "selected_date"  not in st.session_state: st.session_state.selected_date  = today
if "match_result"   not in st.session_state: st.session_state.match_result   = None
if "pending_slot"   not in st.session_state: st.session_state.pending_slot   = None
if "confirm_phone_edit" not in st.session_state: st.session_state.confirm_phone_edit = False


def api_get(path, **params):
    try:
        r = requests.get(f"{API_URL}{path}", params=params, timeout=15)
        return r.json(), r.status_code
    except Exception as exc:
        return {"error": str(exc)}, 500


def api_post(path, json_body):
    try:
        r = requests.post(f"{API_URL}{path}", json=json_body, timeout=15)
        return r.json(), r.status_code
    except Exception as exc:
        return {"error": str(exc)}, 500


def api_delete(path):
    try:
        r = requests.delete(f"{API_URL}{path}", timeout=15)
        return r.json(), r.status_code
    except Exception as exc:
        return {"error": str(exc)}, 500


def reset_booking_flow():
    st.session_state.match_result = None
    st.session_state.pending_slot = None
    st.session_state.confirm_phone_edit = False


# ── Calendar ──────────────────────────────────────────────────────────────────
cal_col, day_col = st.columns([3, 2], gap="large")

with cal_col:
    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("◀ Prev", use_container_width=True):
            m = st.session_state.cal_month - 1
            y = st.session_state.cal_year
            if m == 0:
                m, y = 12, y - 1
            st.session_state.cal_month, st.session_state.cal_year = m, y
            st.rerun()
    with nav2:
        st.markdown(
            f"<h4 style='text-align:center;'>"
            f"{calendar.month_name[st.session_state.cal_month]} {st.session_state.cal_year}"
            f"</h4>",
            unsafe_allow_html=True,
        )
    with nav3:
        if st.button("Next ▶", use_container_width=True):
            m = st.session_state.cal_month + 1
            y = st.session_state.cal_year
            if m == 13:
                m, y = 1, y + 1
            st.session_state.cal_month, st.session_state.cal_year = m, y
            st.rerun()

    if st.button("Today", use_container_width=True):
        st.session_state.cal_year = today.year
        st.session_state.cal_month = today.month
        st.session_state.selected_date = today
        st.rerun()

    month_data, status = api_get(
        "/schedule/month", year=st.session_state.cal_year, month=st.session_state.cal_month
    )
    if status != 200:
        st.error(f"Could not load calendar: {month_data.get('error', 'unknown error')}")
        day_counts = {}
    else:
        day_counts = {int(k): v for k, v in month_data.get("days", {}).items()}

    weekday_cols = st.columns(7)
    for i, wd in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        weekday_cols[i].markdown(f"<div style='text-align:center;font-weight:600;'>{wd}</div>", unsafe_allow_html=True)

    weeks = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)
    for week in weeks:
        cols = st.columns(7)
        for i, day_num in enumerate(week):
            with cols[i]:
                if day_num == 0:
                    st.write("")
                    continue
                counts = day_counts.get(day_num, {"total": 0, "new": 0, "existing": 0})
                this_date = dt.date(st.session_state.cal_year, st.session_state.cal_month, day_num)
                label = str(day_num)
                if counts["total"]:
                    label += f"\n🆕{counts.get('new', 0)} ✅{counts.get('existing', 0)}"
                is_selected = this_date == st.session_state.selected_date
                if st.button(
                    label,
                    key=f"day_{day_num}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    st.session_state.selected_date = this_date
                    reset_booking_flow()
                    st.rerun()

# ── Selected day agenda ────────────────────────────────────────────────────────
with day_col:
    sel = st.session_state.selected_date
    st.subheader(sel.strftime("%A, %B %-d, %Y") if hasattr(sel, "strftime") else str(sel))

    day_data, status = api_get("/schedule/day", date=sel.isoformat())
    if status != 200:
        st.error(f"Could not load sessions: {day_data.get('error', 'unknown error')}")
        sessions = []
    else:
        sessions = day_data.get("sessions", [])

    if not sessions:
        st.info("No re-test slots scheduled for this day yet.")
    for s in sessions:
        tag = "🆕 New Athlete" if s["match_status"] == "new" else "✅ Existing Athlete"
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{s['scheduled_time'][:5]}** — {s['athlete_name']}")
                st.caption(f"{tag} · {s['phone']}")
                if s.get("notes"):
                    st.caption(f"📝 {s['notes']}")
            with c2:
                if st.button("Cancel", key=f"cancel_{s['id']}", use_container_width=True):
                    result, cstatus = api_delete(f"/schedule/session/{s['id']}")
                    if cstatus == 200:
                        st.success("Slot cancelled.")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Could not cancel."))

st.markdown("---")

# ── Add slot ──────────────────────────────────────────────────────────────────
st.subheader("Book a Re-Test Slot")

if st.session_state.match_result is None:
    with st.form("new_slot_form"):
        c1, c2 = st.columns(2)
        with c1:
            athlete_name = st.text_input("Athlete Name", placeholder="First Last")
            phone = st.text_input("Phone Number", placeholder="(555) 555-5555")
        with c2:
            slot_date = st.date_input("Test Date", value=st.session_state.selected_date)
            slot_time = st.time_input("Test Time", value=dt.time(9, 0))
        notes = st.text_area("Notes (optional)", placeholder="e.g. jump testing only")

        submitted = st.form_submit_button("Check Athlete & Continue", type="primary")

    if submitted:
        if not athlete_name.strip() or not phone.strip():
            st.error("Athlete name and phone number are required.")
        else:
            match, mstatus = api_post(
                "/schedule/check_match",
                {"athlete_name": athlete_name.strip(), "phone": phone.strip()},
            )
            if mstatus != 200:
                st.error(match.get("error", "Could not check athlete match."))
            else:
                st.session_state.match_result = match
                st.session_state.pending_slot = {
                    "athlete_name": athlete_name.strip(),
                    "phone": phone.strip(),
                    "scheduled_date": slot_date.isoformat(),
                    "scheduled_time": slot_time.strftime("%H:%M"),
                    "notes": notes.strip() or None,
                }
                st.rerun()

else:
    match = st.session_state.match_result
    slot = st.session_state.pending_slot
    st.write(
        f"**{slot['athlete_name']}** · {slot['phone']} · "
        f"{slot['scheduled_date']} at {slot['scheduled_time']}"
    )

    # Case 1: no athlete found with this name at all → straightforward new athlete
    if not match["name_found"]:
        st.info("No existing athlete matches this name. This will create a new athlete record.")
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if st.button("Book as New Athlete", type="primary", use_container_width=True):
                result, bstatus = api_post("/schedule/book", {**slot, "action": "new"})
                if bstatus == 200:
                    st.success(f"Booked {slot['athlete_name']} for {slot['scheduled_date']} at {slot['scheduled_time']}.")
                    reset_booking_flow()
                    st.rerun()
                else:
                    st.error(result.get("error", "Could not book slot."))
        with bcol2:
            if st.button("Cancel", use_container_width=True):
                reset_booking_flow()
                st.rerun()

    # Case 2: name found and phone matches → clean existing-athlete booking
    elif match["phone_match"]:
        st.success(f"Matches existing athlete: **{match['full_name']}**")
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if st.button("Book Slot", type="primary", use_container_width=True):
                result, bstatus = api_post(
                    "/schedule/book",
                    {**slot, "action": "existing", "master_uid": match["master_uid"]},
                )
                if bstatus == 200:
                    st.success(f"Booked {slot['athlete_name']} for {slot['scheduled_date']} at {slot['scheduled_time']}.")
                    reset_booking_flow()
                    st.rerun()
                else:
                    st.error(result.get("error", "Could not book slot."))
        with bcol2:
            if st.button("Cancel", use_container_width=True, key="cancel_case2"):
                reset_booking_flow()
                st.rerun()

    # Case 3: name found but phone does NOT match on file → conflict, needs resolution
    else:
        st.warning(
            f"An athlete named **{match['full_name']}** already exists, but the phone number "
            f"on file (**{match['stored_phone'] or 'none on file'}**) doesn't match what you "
            f"entered (**{slot['phone']}**)."
        )
        st.write("How would you like to resolve this?")

        rcol1, rcol2 = st.columns(2)
        with rcol1:
            st.markdown("**Option A — Different person, same name**")
            if st.button("Create New Athlete", use_container_width=True):
                result, bstatus = api_post("/schedule/book", {**slot, "action": "new"})
                if bstatus == 200:
                    st.success(f"Booked {slot['athlete_name']} as a new athlete for {slot['scheduled_date']} at {slot['scheduled_time']}.")
                    reset_booking_flow()
                    st.rerun()
                else:
                    st.error(result.get("error", "Could not book slot."))

        with rcol2:
            st.markdown(f"**Option B — Update {match['full_name']}'s phone number**")
            st.caption(
                f"⚠️ This overwrites the phone number PWRX uses to match "
                f"{match['full_name']}'s data across every system (ArmCare, Dari, InBody, "
                f"membership). Only do this if you're sure their number changed."
            )
            st.session_state.confirm_phone_edit = st.checkbox(
                f"I understand this changes {match['full_name']}'s phone number on file.",
                value=st.session_state.confirm_phone_edit,
            )
            if st.button(
                "Confirm & Update Phone",
                use_container_width=True,
                disabled=not st.session_state.confirm_phone_edit,
            ):
                result, bstatus = api_post(
                    "/schedule/book",
                    {**slot, "action": "update_phone", "master_uid": match["master_uid"]},
                )
                if bstatus == 200:
                    st.success(
                        f"Updated phone for {match['full_name']} and booked the slot for "
                        f"{slot['scheduled_date']} at {slot['scheduled_time']}."
                    )
                    reset_booking_flow()
                    st.rerun()
                else:
                    st.error(result.get("error", "Could not book slot."))

        if st.button("Cancel", key="cancel_case3"):
            reset_booking_flow()
            st.rerun()

st.markdown("---")
st.caption("PWRX · Strength & Conditioning Data Platform")
