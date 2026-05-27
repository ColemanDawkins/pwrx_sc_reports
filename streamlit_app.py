import streamlit as st
import requests
import io
import pandas as pd

st.set_page_config(
    page_title="PWRX S&C Reports",
    page_icon="🏋️",
    layout="centered"
)

API_URL = "https://web-production-4f00a.up.railway.app"

st.markdown(
    "<h2 style='text-align:center;color:#E8621A;margin-bottom:0;'>PWRX</h2>"
    "<h4 style='text-align:center;color:#ffffff;margin-top:4px;'>Strength & Conditioning Reports</h4>",
    unsafe_allow_html=True
)
st.markdown("---")

tab1, tab2,git status tab3 = st.tabs(["Generate Report", "Upload Data", "Roster"])


# ── TAB 1: Generate Report ────────────────────────────────────────────────────
with tab1:
    st.markdown("### Generate Athlete Report")
    st.caption("Select an athlete from the database to generate their S&C performance report.")

    try:
        roster_resp = requests.get(API_URL + "/roster", timeout=10)
        roster_data = roster_resp.json().get("roster", [])
    except Exception:
        roster_data = []

    if roster_data:
        # Only show athletes who have at least one data source
        active = [
            r for r in roster_data
            if (r["dari_sessions"] + r["vald_sessions"] + r["armcare_sessions"]) > 0
        ]

        if active:
            player_names = [r["full_name"] for r in active]
            selected = st.selectbox("Select athlete", player_names)

            # Show coverage badge for selected athlete
            match = next((r for r in active if r["full_name"] == selected), None)
            if match:
                cols = st.columns(3)
                cols[0].metric("Dari sessions",   match["dari_sessions"])
                cols[1].metric("Vald sessions",   match["vald_sessions"])
                cols[2].metric("ArmCare sessions", match["armcare_sessions"])

            if st.button("Generate Report", type="primary"):
                with st.spinner("Generating report... ~30 seconds"):
                    try:
                        response = requests.post(
                            API_URL + "/generate_report",
                            data={"athlete_name": selected},
                            timeout=120
                        )
                        if response.status_code == 200:
                            st.success("Report ready!")
                            safe_name = selected.replace(" ", "_")
                            st.download_button(
                                label="Download HTML Report",
                                data=io.BytesIO(response.content),
                                file_name=f"{safe_name}_sc_report.html",
                                mime="text/html"
                            )
                        else:
                            st.error("Error: " + response.text)
                    except Exception as exc:
                        st.error("Connection error: " + str(exc))
        else:
            st.info("No athletes with data yet. Upload files in the Upload Data tab first.")
    else:
        st.info("Could not connect to API or no athletes in database yet.")


# ── TAB 2: Upload Data ────────────────────────────────────────────────────────
with tab2:
    st.markdown("### Upload Data to Database")
    st.caption(
        "Upload a CSV or Excel export for any data source. "
        "Upload **master_uid** first before uploading dataset files."
    )

    source_options = {
        "Master UID (upload first)": "master_uid",
        "PushPress":                 "pushpress",
        "Dari Motion":               "dari_motion",
        "ArmCare":                   "armcare",
        "Vald Performance":          "vald_performance",
    }

    selected_source = st.selectbox("Select data source", list(source_options.keys()))
    table_name = source_options[selected_source]

    upload_file = st.file_uploader(
        f"Select {selected_source} CSV or XLSX file",
        type=["csv", "xlsx", "xls"],
        key="upload"
    )

    if upload_file:
        st.success(f"File loaded: {upload_file.name}")

        if st.button("Upload to Database", type="primary"):
            with st.spinner("Uploading... please wait"):
                try:
                    suffix = ".xlsx" if upload_file.name.endswith((".xlsx", ".xls")) else ".csv"
                    mime   = ("application/vnd.openxmlformats-officedocument"
                              ".spreadsheetml.sheet" if suffix == ".xlsx" else "text/csv")

                    response = requests.post(
                        API_URL + "/ingest",
                        files={"file": (upload_file.name, upload_file.getvalue(), mime)},
                        data={"table": table_name},
                        timeout=300
                    )

                    if response.status_code == 200:
                        result = response.json()
                        flagged = result.get("flagged", 0)
                        st.success(
                            f"Done! {result['inserted']} rows added, "
                            f"{result['skipped']} skipped."
                            + (f" {flagged} rows flagged for review." if flagged else "")
                        )

                        warnings = [w for w in result.get("warnings", []) if "WARNING" in w]
                        if warnings:
                            with st.expander(f"Data quality notes ({len(warnings)})"):
                                for w in warnings:
                                    st.warning(w)
                    else:
                        st.error("Error: " + response.text)

                except Exception as exc:
                    st.error("Connection error: " + str(exc))


# ── TAB 3: Roster ─────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### Athletes in Database")

    if st.button("Refresh"):
        st.rerun()

    try:
        roster_resp2 = requests.get(API_URL + "/roster", timeout=10)
        roster_data2 = roster_resp2.json().get("roster", [])
    except Exception:
        roster_data2 = []

    if roster_data2:
        df = pd.DataFrame(roster_data2)
        df = df[["full_name", "dari_sessions", "vald_sessions",
                 "armcare_sessions", "pushpress_records",
                 "last_dari", "last_vald", "last_armcare"]]
        df.columns = ["Athlete", "Dari", "Vald", "ArmCare",
                      "PushPress", "Last Dari", "Last Vald", "Last ArmCare"]
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(roster_data2)} athletes in database")
    else:
        st.info("No athletes in database yet.")

st.markdown("---")
st.caption("PWRX · Strength & Conditioning Data Platform")
