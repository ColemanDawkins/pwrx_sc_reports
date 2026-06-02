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

tab1, tab2, tab3, tab4 = st.tabs(["Generate Report", "Upload Data", "Athletes", "Roster"])


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
        active = [
            r for r in roster_data
            if (r["dari_sessions"] + r["vald_sessions"] + r["armcare_sessions"]) > 0
        ]
        if active:
            player_names = [r["full_name"] for r in active]
            selected     = st.selectbox("Select athlete", player_names)
            match        = next((r for r in active if r["full_name"] == selected), None)
            if match:
                cols = st.columns(3)
                cols[0].metric("Dari sessions",    match["dari_sessions"])
                cols[1].metric("Vald sessions",    match["vald_sessions"])
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
    st.caption("Upload a CSV or Excel export for any data source. Upload Master UID first.")

    source_options = {
        "Master UID (upload first)": "master_uid",
        "PushPress":                 "pushpress",
        "Dari Motion":               "dari_motion",
        "ArmCare":                   "armcare",
        "Vald Performance":          "vald_performance",
    }

    selected_source = st.selectbox("Select data source", list(source_options.keys()))
    table_name      = source_options[selected_source]
    upload_file     = st.file_uploader(
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
                        result   = response.json()
                        flagged  = result.get("flagged", 0)
                        unlinked = result.get("unlinked_names", [])
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

                        # ── Unlinked athletes found in upload ──────────────
                        if unlinked:
                            st.markdown("---")
                            st.warning(
                                f"**{len(unlinked)} athlete(s) in this file have no PWRX ID.** "
                                "Create their master records below."
                            )
                            for row in unlinked:
                                fname = row.get("first_name") or ""
                                lname = row.get("last_name") or ""
                                full  = row.get("full_name", "Unknown")
                                col1, col2 = st.columns([3, 1])
                                col1.write(f"**{full}**")
                                if col2.button("Create PWRX ID", key=f"create_{full}"):
                                    with st.spinner(f"Creating record for {full}..."):
                                        resp2 = requests.post(
                                            API_URL + "/athletes/create_from_import",
                                            json={
                                                "table":      table_name,
                                                "first_name": fname or full.split()[0],
                                                "last_name":  lname or " ".join(full.split()[1:]),
                                            },
                                            timeout=30
                                        )
                                        if resp2.status_code == 200:
                                            r2 = resp2.json()
                                            st.success(
                                                f"Created {r2['master_uid']} for {r2['full_name']}. "
                                                f"{r2.get('rows_linked', 0)} rows linked."
                                            )
                                        elif resp2.status_code == 409:
                                            r2 = resp2.json()
                                            st.info(
                                                f"Already exists: {r2['existing_uid']} — {r2['existing_name']}"
                                            )
                                        else:
                                            st.error("Error: " + resp2.text)
                    else:
                        st.error("Error: " + response.text)
                except Exception as exc:
                    st.error("Connection error: " + str(exc))


# ── TAB 3: Athletes ───────────────────────────────────────────────────────────
with tab3:
    st.markdown("### Athlete Management")

    # ── Section A: Manual creation ────────────────────────────────────────────
    st.markdown("#### Add New Athlete")
    st.caption("Creates a new PWRX master record. Checks for duplicates before creating.")

    with st.form("create_athlete_form"):
        col1, col2 = st.columns(2)
        new_first  = col1.text_input("First name")
        new_last   = col2.text_input("Last name")
        submitted  = st.form_submit_button("Create Athlete", type="primary")

    if submitted:
        if not new_first.strip() or not new_last.strip():
            st.error("First name and last name are both required.")
        else:
            # Preview search first
            full_preview = f"{new_first.strip()} {new_last.strip()}"
            with st.spinner(f"Checking for existing records matching '{full_preview}'..."):
                try:
                    srch = requests.get(
                        API_URL + "/athletes/search",
                        params={"q": full_preview},
                        timeout=10
                    )
                    matches = srch.json().get("results", []) if srch.status_code == 200 else []
                except Exception:
                    matches = []

            if matches:
                st.warning(
                    f"Found {len(matches)} possible match(es) for '{full_preview}'. "
                    "Review before creating to avoid duplicates."
                )
                for m in matches[:5]:
                    st.info(f"**{m['master_uid']}** — {m['full_name']}")
                if st.button("Create anyway (not a duplicate)", key="force_create"):
                    _do_create = True
                else:
                    _do_create = False
            else:
                _do_create = True

            if _do_create:
                with st.spinner("Creating athlete..."):
                    try:
                        resp = requests.post(
                            API_URL + "/athletes/create",
                            json={"first_name": new_first.strip(), "last_name": new_last.strip()},
                            timeout=15
                        )
                        if resp.status_code == 200:
                            r = resp.json()
                            st.success(
                                f"Created **{r['master_uid']}** for **{r['full_name']}**"
                            )
                        elif resp.status_code == 409:
                            r = resp.json()
                            st.warning(
                                f"Skipped — duplicate found: **{r['existing_uid']}** — {r['existing_name']}"
                            )
                        else:
                            st.error("Error: " + resp.text)
                    except Exception as exc:
                        st.error("Connection error: " + str(exc))

    st.markdown("---")

    # ── Section B: Re-link All ────────────────────────────────────────────────
    st.markdown("#### Re-link Unmatched Rows")
    st.caption(
        "Scans all source tables and links rows to master_uid by name matching. "
        "Run this after adding new athletes or uploading data."
    )

    col_a, col_b = st.columns([2, 1])
    run_all  = col_a.button("Re-link All Tables", type="primary")
    table_sel = col_b.selectbox(
        "Or single table",
        ["All", "dari_motion", "vald_performance", "armcare", "pushpress"],
        label_visibility="collapsed"
    )

    if run_all:
        tbl_param = None if table_sel == "All" else table_sel
        with st.spinner("Running name-match sweep..."):
            try:
                resp = requests.post(
                    API_URL + "/backfill",
                    params={"table": tbl_param} if tbl_param else {},
                    timeout=60
                )
                if resp.status_code == 200:
                    r = resp.json()
                    st.success(f"Complete — {r['total_linked']} rows linked total.")
                    linked = r.get("linked", {})
                    if linked:
                        for tbl, count in linked.items():
                            st.write(f"• **{tbl}**: {count} rows linked")
                else:
                    st.error("Error: " + resp.text)
            except Exception as exc:
                st.error("Connection error: " + str(exc))

    st.markdown("---")

    # ── Section C: Athlete search ─────────────────────────────────────────────
    st.markdown("#### Search Athletes")
    search_q = st.text_input("Search by name", placeholder="e.g. Isaac")
    if search_q and len(search_q) >= 2:
        try:
            srch = requests.get(
                API_URL + "/athletes/search",
                params={"q": search_q},
                timeout=10
            )
            results = srch.json().get("results", []) if srch.status_code == 200 else []
        except Exception:
            results = []

        if results:
            df_srch = pd.DataFrame(results)[["master_uid", "full_name", "dari_id", "armcare_id", "vald_id", "pushpress_id"]]
            df_srch.columns = ["PWRX ID", "Name", "Dari ID", "ArmCare ID", "Vald ID", "PushPress ID"]
            st.dataframe(df_srch, use_container_width=True, hide_index=True)
        else:
            st.info("No athletes found.")


# ── TAB 4: Roster ─────────────────────────────────────────────────────────────
with tab4:
    st.markdown("### Athletes in Database")

    if st.button("Refresh"):
        st.rerun()

    try:
        roster_resp2  = requests.get(API_URL + "/roster", timeout=10)
        roster_json   = roster_resp2.json()
        roster_data2  = roster_json.get("roster", [])
        unlinked_cnts = roster_json.get("unlinked_counts", {})
    except Exception:
        roster_data2  = []
        unlinked_cnts = {}

    if unlinked_cnts:
        total_unlinked = sum(unlinked_cnts.values())
        if total_unlinked > 0:
            st.warning(
                f"**{total_unlinked} rows across all tables have no PWRX ID link.** "
                "Use the Athletes tab → Re-link All to fix."
            )
            cols = st.columns(4)
            for i, (tbl, cnt) in enumerate(unlinked_cnts.items()):
                cols[i].metric(tbl.replace("_", " ").title(), f"{cnt} unlinked")

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
