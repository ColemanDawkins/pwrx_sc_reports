"""
sc_db.py
--------------------------------------------------------------------------------
PWRX Strength & Conditioning -- PostgreSQL Database Layer

Mirrors the pattern of pwrx_db.py from pitchingwrx-reports.
Uses psycopg2 + DATABASE_URL env var (same as Railway deployment).

Tables managed:
    master_uid         -- central athlete identity / linking table
    pushpress          -- membership & CRM data
    dari_motion        -- movement screening (177-col Dari export)
    armcare            -- arm strength & ROM (ArmCare.com)
    vald_performance   -- force plate / jump metrics (Vald)

Usage:
    python sc_db.py --init                           # create all tables
    python sc_db.py master_uid.csv --table master_uid
    python sc_db.py dari_export.csv --table dari_motion
    python sc_db.py --athlete "Isaac Stebens"        # print session counts
"""

import os
import sys
import argparse
import datetime

import psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np

DATABASE_URL = os.environ.get("DATABASE_URL")

MAX_SESSIONS = 4   # last N sessions pulled for reports


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS master_uid (
    id              SERIAL PRIMARY KEY,
    master_uid      TEXT UNIQUE NOT NULL,
    first_name      TEXT,
    last_name       TEXT,
    full_name       TEXT NOT NULL,
    pushpress_id    TEXT UNIQUE,
    dari_id         TEXT UNIQUE,
    armcare_id      TEXT UNIQUE,
    vald_id         TEXT UNIQUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pushpress (
    id                              SERIAL PRIMARY KEY,
    master_uid                      TEXT REFERENCES master_uid(master_uid) ON DELETE SET NULL,
    member_id                       TEXT UNIQUE NOT NULL,
    first_name                      TEXT,
    last_name                       TEXT,
    email                           TEXT,
    gender                          TEXT,
    dob                             DATE,
    phone                           TEXT,
    address                         TEXT,
    city                            TEXT,
    state                           TEXT,
    postal_code                     TEXT,
    plan                            TEXT,
    status                          TEXT,
    plan_status                     TEXT,
    member_since                    DATE,
    plan_start_date                 DATE,
    plan_cancel_date                DATE,
    is_member                       BOOLEAN,
    first_checkin                   DATE,
    last_checkin                    DATE,
    uploaded_at                     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dari_motion (
    id                  SERIAL PRIMARY KEY,
    master_uid          TEXT REFERENCES master_uid(master_uid) ON DELETE SET NULL,
    dari_id             TEXT,
    session_guid        TEXT UNIQUE,
    athlete_name        TEXT,
    version             TEXT,
    session_ts          TIMESTAMPTZ,
    session_height      NUMERIC,
    session_weight      NUMERIC,
    unit_mode           TEXT,
    score_overall                           NUMERIC,
    score_function                          NUMERIC,
    score_function_squat                    NUMERIC,
    score_function_slr                      NUMERIC,
    score_function_sll                      NUMERIC,
    score_function_avg                      NUMERIC,
    score_explosive                         NUMERIC,
    score_explosive_vj                      NUMERIC,
    score_explosive_vjr                     NUMERIC,
    score_explosive_vjl                     NUMERIC,
    score_explosive_cvj                     NUMERIC,
    score_explosive_dbj                     NUMERIC,
    score_explosive_avg                     NUMERIC,
    score_dysfunction                       NUMERIC,
    score_vulnerability                     NUMERIC,
    focus_0_code TEXT, focus_0_name TEXT, focus_0_score NUMERIC,
    focus_1_code TEXT, focus_1_name TEXT, focus_1_score NUMERIC,
    focus_2_code TEXT, focus_2_name TEXT, focus_2_score NUMERIC,
    anklt_vulnerability NUMERIC, anklt_count INT, anklt_mb NUMERIC, anklt_kn NUMERIC,
    ankrt_vulnerability NUMERIC, ankrt_count INT, ankrt_mb NUMERIC, ankrt_kn NUMERIC,
    knelt_vulnerability NUMERIC, knelt_count INT, knelt_mb NUMERIC, knelt_allo NUMERIC, knelt_alla NUMERIC, knelt_kn NUMERIC,
    knert_vulnerability NUMERIC, knert_count INT, knert_mb NUMERIC, knert_allo NUMERIC, knert_alla NUMERIC, knert_kn NUMERIC,
    hiplt_vulnerability NUMERIC, hiplt_count INT, hiplt_mb NUMERIC, hiplt_kn NUMERIC,
    hiprt_vulnerability NUMERIC, hiprt_count INT, hiprt_mb NUMERIC, hiprt_kn NUMERIC,
    sholt_vulnerability NUMERIC, sholt_count INT, sholt_mb NUMERIC, sholt_al NUMERIC,
    short_vulnerability NUMERIC, short_count INT, short_mb NUMERIC, short_al NUMERIC,
    spnlo_vulnerability NUMERIC, spnlo_count INT, spnlo_mb NUMERIC, spnlo_al NUMERIC, spnlo_sw NUMERIC,
    spnup_vulnerability NUMERIC, spnup_count INT, spnup_mb NUMERIC, spnup_al NUMERIC,
    muscle_hipl TEXT, muscle_hipr TEXT, muscle_kneel TEXT, muscle_kneer TEXT,
    muscle_anklel TEXT, muscle_ankler TEXT, muscle_psoasl TEXT, muscle_psoasr TEXT,
    dp1_left_shoulder_angle_max NUMERIC, dp1_right_shoulder_angle_max NUMERIC,
    dp2_left_shoulder_angle_min NUMERIC, dp2_right_shoulder_angle_min NUMERIC,
    dp7_jump_height NUMERIC,
    dp7_left_hip_takeoff_torque_pct NUMERIC, dp7_left_knee_takeoff_torque_pct NUMERIC,
    dp7_left_ankle_takeoff_torque_pct NUMERIC,
    dp7_right_hip_takeoff_torque_pct NUMERIC, dp7_right_knee_takeoff_torque_pct NUMERIC,
    dp7_right_ankle_takeoff_torque_pct NUMERIC,
    dp7_grf_max NUMERIC, dp7_net_impulse NUMERIC, dp7_rfd NUMERIC,
    dp9_squat_depth NUMERIC,
    dp9_right_hip_flexion NUMERIC, dp9_right_knee_flexion NUMERIC, dp9_right_ankle_flexion NUMERIC,
    dp9_kne_dyn_val_max_r NUMERIC,
    dp10_squat_depth NUMERIC,
    dp10_left_hip_flexion NUMERIC, dp10_left_knee_flexion NUMERIC, dp10_left_ankle_flexion NUMERIC,
    dp10_kne_dyn_val_max_l NUMERIC,
    dp11_jump_height NUMERIC, dp11_grf_max NUMERIC, dp11_net_impulse NUMERIC, dp11_rfd NUMERIC,
    dp12_jump_height NUMERIC, dp12_grf_max NUMERIC, dp12_net_impulse NUMERIC, dp12_rfd NUMERIC,
    dp15_left_shoulder_ext NUMERIC, dp15_right_shoulder_ext NUMERIC,
    dp15_left_shoulder_int NUMERIC, dp15_right_shoulder_int NUMERIC,
    dp16_left_shoulder_max NUMERIC, dp16_right_shoulder_max NUMERIC,
    dp16_left_shoulder_min NUMERIC, dp16_right_shoulder_min NUMERIC,
    dp19_jump_height NUMERIC, dp19_grf_max NUMERIC, dp19_net_impulse NUMERIC, dp19_stance_time NUMERIC,
    dp45_jump_height NUMERIC, dp45_grf_max NUMERIC, dp45_net_impulse NUMERIC, dp45_rfd NUMERIC,
    dp151_st_ln_max NUMERIC,
    dp152_st_ln_max NUMERIC,
    dp156_squat_depth NUMERIC,
    dp156_left_hip_flexion NUMERIC, dp156_left_knee_flexion NUMERIC, dp156_left_ankle_flexion NUMERIC,
    dp156_right_hip_flexion NUMERIC, dp156_right_knee_flexion NUMERIC, dp156_right_ankle_flexion NUMERIC,
    dp156_pct_diff_max_l NUMERIC, dp156_pct_diff_max_r NUMERIC,
    dp157_th_rot_e3 NUMERIC, dp157_lum_rot_e3 NUMERIC,
    dp158_th_rot_e3 NUMERIC, dp158_lum_rot_e3 NUMERIC,
    dp163_rbalance_lt_xrom NUMERIC, dp163_rbalance_lt_yrom NUMERIC,
    dp164_lbalance_lt_xrom NUMERIC, dp164_lbalance_lt_yrom NUMERIC,
    uploaded_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS armcare (
    id                  SERIAL PRIMARY KEY,
    master_uid          TEXT REFERENCES master_uid(master_uid) ON DELETE SET NULL,
    armcare_id          TEXT,
    exam_date           DATE,
    first_name          TEXT,
    last_name           TEXT,
    email               TEXT,
    arm_score           NUMERIC,
    total_strength      NUMERIC,
    shoulder_balance    NUMERIC,
    svr                 NUMERIC,
    irtarm_strength     NUMERIC,
    ertarm_strength     NUMERIC,
    velo                NUMERIC,
    irtarm_rom          NUMERIC,
    ertarm_rom          NUMERIC,
    throws              TEXT,
    position_1          TEXT,
    playing_level       TEXT,
    uploaded_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vald_performance (
    id                          SERIAL PRIMARY KEY,
    master_uid                  TEXT REFERENCES master_uid(master_uid) ON DELETE SET NULL,
    vald_external_id            TEXT,
    athlete_name                TEXT,
    test_type                   TEXT,
    test_date                   DATE,
    bw_kg                       NUMERIC,
    jump_height_flight_in       NUMERIC,
    peak_power_w                NUMERIC,
    rsi_modified                NUMERIC,
    eccentric_peak_force_n      NUMERIC,
    concentric_impulse_100ms    NUMERIC,
    jump_height_imp_mom_in      NUMERIC,
    eccentric_peak_power_per_bm NUMERIC,
    bodyweight_lbs              NUMERIC,
    uploaded_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dari_master     ON dari_motion(master_uid);
CREATE INDEX IF NOT EXISTS idx_dari_ts         ON dari_motion(session_ts);
CREATE INDEX IF NOT EXISTS idx_armcare_master  ON armcare(master_uid);
CREATE INDEX IF NOT EXISTS idx_armcare_date    ON armcare(exam_date);
CREATE INDEX IF NOT EXISTS idx_vald_master     ON vald_performance(master_uid);
CREATE INDEX IF NOT EXISTS idx_vald_date       ON vald_performance(test_date);
CREATE INDEX IF NOT EXISTS idx_pushpress_master ON pushpress(master_uid);
"""


# ─────────────────────────────────────────────────────────────────────────────
# COLUMN ALIASES  (same approach as pwrx_db.py)
# Maps canonical DB column -> list of known aliases from export files
# ─────────────────────────────────────────────────────────────────────────────

COLUMN_ALIASES = {
    # master_uid
    "master_uid":   ["master_uid", "masteruid", "master uid", "uid"],
    "first_name":   ["first_name", "firstname", "first", "First Name"],
    "last_name":    ["last_name", "lastname", "last", "Last Name"],
    "full_name":    ["full_name", "fullname", "name", "Full Name", "athlete"],
    "pushpress_id": ["pushpress_id", "memberId", "member_id", "MemberId"],
    "dari_id":      ["dari_id", "meta__person__unique_id", "DariID"],
    "armcare_id":   ["armcare_id", "ArmCare ID", "armcareid", "ArmCareID"],
    "vald_id":      ["vald_id", "ExternalId", "externalid", "ValdID"],
    # pushpress
    "member_id":    ["memberId", "member_id", "MemberId", "memberid"],
    "plan":         ["plan", "Plan"],
    "status":       ["status", "Status"],
    "plan_status":  ["planStatus", "plan_status", "PlanStatus"],
    "member_since": ["memberSince", "member_since", "MemberSince"],
    "is_member":    ["isMember", "is_member", "IsMember"],
    "first_checkin":["firstCheckin", "first_checkin", "FirstCheckin"],
    "last_checkin": ["lastCheckin", "last_checkin", "LastCheckin"],
    # dari
    "session_guid": ["meta__session__session_guid", "session_guid"],
    "athlete_name": ["name", "athlete_name", "Name"],
    "session_ts":   ["timestamp", "meta__session__session_timestamp", "session_ts"],
    "session_height": ["meta__session__session_height", "session_height"],
    "session_weight": ["meta__session__session_weight", "session_weight"],
    "unit_mode":    ["meta__session__unit_mode", "unit_mode"],
    "score_overall": ["summary__scores__athleticism__overall", "score_overall"],
    "score_function": ["summary__scores__athleticism__function", "score_function"],
    "score_function_squat": ["summary__scores__athleticism__function_index__squat", "score_function_squat"],
    "score_function_slr": ["summary__scores__athleticism__function_index__slr", "score_function_slr"],
    "score_function_sll": ["summary__scores__athleticism__function_index__sll", "score_function_sll"],
    "score_function_avg": ["summary__scores__athleticism__function_index__avg", "score_function_avg"],
    "score_explosive": ["summary__scores__athleticism__explosive", "score_explosive"],
    "score_explosive_vj": ["summary__scores__athleticism__explosive_index__vj", "score_explosive_vj"],
    "score_explosive_vjr": ["summary__scores__athleticism__explosive_index__vjr", "score_explosive_vjr"],
    "score_explosive_vjl": ["summary__scores__athleticism__explosive_index__vjl", "score_explosive_vjl"],
    "score_explosive_cvj": ["summary__scores__athleticism__explosive_index__cvj", "score_explosive_cvj"],
    "score_explosive_dbj": ["summary__scores__athleticism__explosive_index__dbj", "score_explosive_dbj"],
    "score_explosive_avg": ["summary__scores__athleticism__explosive_index__avg", "score_explosive_avg"],
    "score_dysfunction": ["summary__scores__athleticism__dysfunction", "score_dysfunction"],
    "score_vulnerability": ["summary__scores__vulnerability", "score_vulnerability"],
    "focus_0_code": ["summary__focus__0__code", "focus_0_code"],
    "focus_0_name": ["summary__focus__0__name", "focus_0_name"],
    "focus_0_score": ["summary__focus__0__score", "focus_0_score"],
    "focus_1_code": ["summary__focus__1__code", "focus_1_code"],
    "focus_1_name": ["summary__focus__1__name", "focus_1_name"],
    "focus_1_score": ["summary__focus__1__score", "focus_1_score"],
    "focus_2_code": ["summary__focus__2__code", "focus_2_code"],
    "focus_2_name": ["summary__focus__2__name", "focus_2_name"],
    "focus_2_score": ["summary__focus__2__score", "focus_2_score"],
    "anklt_vulnerability": ["summary__joints__ANKLT__vulnerability"],
    "anklt_count": ["summary__joints__ANKLT__count"],
    "anklt_mb": ["summary__joints__ANKLT__group_scores__MB"],
    "anklt_kn": ["summary__joints__ANKLT__group_scores__KN"],
    "ankrt_vulnerability": ["summary__joints__ANKRT__vulnerability"],
    "ankrt_count": ["summary__joints__ANKRT__count"],
    "ankrt_mb": ["summary__joints__ANKRT__group_scores__MB"],
    "ankrt_kn": ["summary__joints__ANKRT__group_scores__KN"],
    "knelt_vulnerability": ["summary__joints__KNELT__vulnerability"],
    "knelt_count": ["summary__joints__KNELT__count"],
    "knelt_mb": ["summary__joints__KNELT__group_scores__MB"],
    "knelt_allo": ["summary__joints__KNELT__group_scores__ALLO"],
    "knelt_alla": ["summary__joints__KNELT__group_scores__ALLA"],
    "knelt_kn": ["summary__joints__KNELT__group_scores__KN"],
    "knert_vulnerability": ["summary__joints__KNERT__vulnerability"],
    "knert_count": ["summary__joints__KNERT__count"],
    "knert_mb": ["summary__joints__KNERT__group_scores__MB"],
    "knert_allo": ["summary__joints__KNERT__group_scores__ALLO"],
    "knert_alla": ["summary__joints__KNERT__group_scores__ALLA"],
    "knert_kn": ["summary__joints__KNERT__group_scores__KN"],
    "hiplt_vulnerability": ["summary__joints__HIPLT__vulnerability"],
    "hiplt_count": ["summary__joints__HIPLT__count"],
    "hiplt_mb": ["summary__joints__HIPLT__group_scores__MB"],
    "hiplt_kn": ["summary__joints__HIPLT__group_scores__KN"],
    "hiprt_vulnerability": ["summary__joints__HIPRT__vulnerability"],
    "hiprt_count": ["summary__joints__HIPRT__count"],
    "hiprt_mb": ["summary__joints__HIPRT__group_scores__MB"],
    "hiprt_kn": ["summary__joints__HIPRT__group_scores__KN"],
    "sholt_vulnerability": ["summary__joints__SHOLT__vulnerability"],
    "sholt_count": ["summary__joints__SHOLT__count"],
    "sholt_mb": ["summary__joints__SHOLT__group_scores__MB"],
    "sholt_al": ["summary__joints__SHOLT__group_scores__AL"],
    "short_vulnerability": ["summary__joints__SHORT__vulnerability"],
    "short_count": ["summary__joints__SHORT__count"],
    "short_mb": ["summary__joints__SHORT__group_scores__MB"],
    "short_al": ["summary__joints__SHORT__group_scores__AL"],
    "spnlo_vulnerability": ["summary__joints__SPNLO__vulnerability"],
    "spnlo_count": ["summary__joints__SPNLO__count"],
    "spnlo_mb": ["summary__joints__SPNLO__group_scores__MB"],
    "spnlo_al": ["summary__joints__SPNLO__group_scores__AL"],
    "spnlo_sw": ["summary__joints__SPNLO__group_scores__SW"],
    "spnup_vulnerability": ["summary__joints__SPNUP__vulnerability"],
    "spnup_count": ["summary__joints__SPNUP__count"],
    "spnup_mb": ["summary__joints__SPNUP__group_scores__MB"],
    "spnup_al": ["summary__joints__SPNUP__group_scores__AL"],
    "muscle_hipl": ["summary__muscles__HipL"],
    "muscle_hipr": ["summary__muscles__HipR"],
    "muscle_kneel": ["summary__muscles__KneeL"],
    "muscle_kneer": ["summary__muscles__KneeR"],
    "muscle_anklel": ["summary__muscles__AnkleL"],
    "muscle_ankler": ["summary__muscles__AnkleR"],
    "muscle_psoasl": ["summary__muscles__PsoasL"],
    "muscle_psoasr": ["summary__muscles__PsoasR"],
    "dp1_left_shoulder_angle_max": ["datapoints__1__0__left_shoulder_angle_max"],
    "dp1_right_shoulder_angle_max": ["datapoints__1__0__right_shoulder_angle_max"],
    "dp2_left_shoulder_angle_min": ["datapoints__2__0__left_shoulder_angle_min"],
    "dp2_right_shoulder_angle_min": ["datapoints__2__0__right_shoulder_angle_min"],
    "dp7_jump_height": ["datapoints__7__0__jump_height"],
    "dp7_left_hip_takeoff_torque_pct": ["datapoints__7__0__left_hip_takeoff_torque_pct"],
    "dp7_left_knee_takeoff_torque_pct": ["datapoints__7__0__left_knee_takeoff_torque_pct"],
    "dp7_left_ankle_takeoff_torque_pct": ["datapoints__7__0__left_ankle_takeoff_torque_pct"],
    "dp7_right_hip_takeoff_torque_pct": ["datapoints__7__0__right_hip_takeoff_torque_pct"],
    "dp7_right_knee_takeoff_torque_pct": ["datapoints__7__0__right_knee_takeoff_torque_pct"],
    "dp7_right_ankle_takeoff_torque_pct": ["datapoints__7__0__right_ankle_takeoff_torque_pct"],
    "dp7_grf_max": ["datapoints__7__0__grf_max"],
    "dp7_net_impulse": ["datapoints__7__0__net_impulse"],
    "dp7_rfd": ["datapoints__7__0__rfd"],
    "dp9_squat_depth": ["datapoints__9__0__squat_depth"],
    "dp9_right_hip_flexion": ["datapoints__9__0__right_hip_flexion_before_lowpoint"],
    "dp9_right_knee_flexion": ["datapoints__9__0__right_knee_flexion_before_lowpoint"],
    "dp9_right_ankle_flexion": ["datapoints__9__0__right_ankle_flexion_before_lowpoint"],
    "dp9_kne_dyn_val_max_r": ["datapoints__9__0__kne_dyn_val_max_R"],
    "dp10_squat_depth": ["datapoints__10__0__squat_depth"],
    "dp10_left_hip_flexion": ["datapoints__10__0__left_hip_flexion_before_lowpoint"],
    "dp10_left_knee_flexion": ["datapoints__10__0__left_knee_flexion_before_lowpoint"],
    "dp10_left_ankle_flexion": ["datapoints__10__0__left_ankle_flexion_before_lowpoint"],
    "dp10_kne_dyn_val_max_l": ["datapoints__10__0__kne_dyn_val_max_L"],
    "dp11_jump_height": ["datapoints__11__0__jump_height"],
    "dp11_grf_max": ["datapoints__11__0__grf_max"],
    "dp11_net_impulse": ["datapoints__11__0__net_impulse"],
    "dp11_rfd": ["datapoints__11__0__rfd"],
    "dp12_jump_height": ["datapoints__12__0__jump_height"],
    "dp12_grf_max": ["datapoints__12__0__grf_max"],
    "dp12_net_impulse": ["datapoints__12__0__net_impulse"],
    "dp12_rfd": ["datapoints__12__0__rfd"],
    "dp15_left_shoulder_ext": ["datapoints__15__0__left_shoulder_angle_ext"],
    "dp15_right_shoulder_ext": ["datapoints__15__0__right_shoulder_angle_ext"],
    "dp15_left_shoulder_int": ["datapoints__15__0__left_shoulder_angle_int"],
    "dp15_right_shoulder_int": ["datapoints__15__0__right_shoulder_angle_int"],
    "dp16_left_shoulder_max": ["datapoints__16__0__left_shoulder_angle_max"],
    "dp16_right_shoulder_max": ["datapoints__16__0__right_shoulder_angle_max"],
    "dp16_left_shoulder_min": ["datapoints__16__0__left_shoulder_angle_min"],
    "dp16_right_shoulder_min": ["datapoints__16__0__right_shoulder_angle_min"],
    "dp19_jump_height": ["datapoints__19__0__jump_height"],
    "dp19_grf_max": ["datapoints__19__0__grf_max"],
    "dp19_net_impulse": ["datapoints__19__0__net_impulse"],
    "dp19_stance_time": ["datapoints__19__0__stance_time"],
    "dp45_jump_height": ["datapoints__45__0__jump_height"],
    "dp45_grf_max": ["datapoints__45__0__grf_max"],
    "dp45_net_impulse": ["datapoints__45__0__net_impulse"],
    "dp45_rfd": ["datapoints__45__0__rfd"],
    "dp151_st_ln_max": ["datapoints__151__0__st_ln_max"],
    "dp152_st_ln_max": ["datapoints__152__0__st_ln_max"],
    "dp156_squat_depth": ["datapoints__156__0__squat_depth"],
    "dp156_left_hip_flexion": ["datapoints__156__0__left_hip_flexion_before_lowpoint"],
    "dp156_left_knee_flexion": ["datapoints__156__0__left_knee_flexion_before_lowpoint"],
    "dp156_left_ankle_flexion": ["datapoints__156__0__left_ankle_flexion_before_lowpoint"],
    "dp156_right_hip_flexion": ["datapoints__156__0__right_hip_flexion_before_lowpoint"],
    "dp156_right_knee_flexion": ["datapoints__156__0__right_knee_flexion_before_lowpoint"],
    "dp156_right_ankle_flexion": ["datapoints__156__0__right_ankle_flexion_before_lowpoint"],
    "dp156_pct_diff_max_l": ["datapoints__156__0__pct_diff_max_L"],
    "dp156_pct_diff_max_r": ["datapoints__156__0__pct_diff_max_R"],
    "dp157_th_rot_e3": ["datapoints__157__0__th_rot_E3"],
    "dp157_lum_rot_e3": ["datapoints__157__0__lum_rot_E3"],
    "dp158_th_rot_e3": ["datapoints__158__0__th_rot_E3"],
    "dp158_lum_rot_e3": ["datapoints__158__0__lum_rot_E3"],
    "dp163_rbalance_lt_xrom": ["datapoints__163__0__rbalance_lt_xrom"],
    "dp163_rbalance_lt_yrom": ["datapoints__163__0__rbalance_lt_yrom"],
    "dp164_lbalance_lt_xrom": ["datapoints__164__0__lbalance_lt_xrom"],
    "dp164_lbalance_lt_yrom": ["datapoints__164__0__lbalance_lt_yrom"],
    # armcare
    "armcare_id":   ["ArmCare ID", "armcare_id", "ArmCareID"],
    "exam_date":    ["Exam Date", "exam_date", "examDate", "date", "Date"],
    "arm_score":    ["Arm Score", "arm_score", "armScore"],
    "total_strength":["Total Strength", "total_strength", "totalStrength"],
    "shoulder_balance":["Shoulder Balance", "shoulder_balance"],
    "svr":          ["SVR", "svr"],
    "irtarm_strength":["IRTARM Strength", "irtarm_strength"],
    "ertarm_strength":["ERTARM Strength", "ertarm_strength"],
    "velo":         ["Velo", "velo", "velocity"],
    "irtarm_rom":   ["IRTARM ROM", "irtarm_rom"],
    "ertarm_rom":   ["ERTARM ROM", "ertarm_rom"],
    "throws":       ["Throws", "throws"],
    "position_1":   ["Position 1", "position_1", "position"],
    "playing_level":["Playing Level", "playing_level"],
    # vald
    "vald_external_id":["ExternalId", "externalid", "vald_external_id", "external_id"],
    "athlete_name": ["Name", "name", "athlete_name", "athleteName"],
    "test_type":    ["Test Type", "test_type", "testType"],
    "test_date":    ["Date", "date", "test_date", "testDate"],
    "bw_kg":        ["BW [KG]", "bw_kg", "bodyweight_kg"],
    "jump_height_flight_in":["Jump Height (Flight Time) in Inches [in] ", "jump_height_flight_in"],
    "peak_power_w": ["Peak Power [W] ", "peak_power_w", "peak_power"],
    "rsi_modified": ["RSI-modified [m/s] ", "rsi_modified", "rsi"],
    "eccentric_peak_force_n":["Eccentric Peak Force [N] ", "eccentric_peak_force_n"],
    "concentric_impulse_100ms":["Concentric Impulse-100ms [N s] ", "concentric_impulse_100ms"],
    "jump_height_imp_mom_in":["Jump Height (Imp-Mom) in Inches [in] ", "jump_height_imp_mom_in"],
    "eccentric_peak_power_per_bm":["Eccentric Peak Power / BM [W/kg] ", "eccentric_peak_power_per_bm"],
    "bodyweight_lbs":["Bodyweight in Pounds [lbs] ", "bodyweight_lbs"],
}

# Which column is the unique key per table (used for ON CONFLICT)
TABLE_UNIQUE_KEY = {
    "master_uid":       "master_uid",
    "pushpress":        "member_id",
    "dari_motion":      "session_guid",
    "armcare":          None,   # no natural unique key — insert always
    "vald_performance": None,
}

# Columns to insert per table (in order)
TABLE_COLUMNS = {
    "master_uid": [
        "master_uid", "first_name", "last_name", "full_name",
        "pushpress_id", "dari_id", "armcare_id", "vald_id",
    ],
    "pushpress": [
        "master_uid", "member_id", "first_name", "last_name", "email",
        "gender", "dob", "phone", "address", "city", "state", "postal_code",
        "plan", "status", "plan_status", "member_since", "plan_start_date",
        "plan_cancel_date", "is_member", "first_checkin", "last_checkin",
    ],
    "dari_motion": [
        "master_uid", "dari_id", "session_guid", "athlete_name", "version",
        "session_ts", "session_height", "session_weight", "unit_mode",
        "score_overall", "score_function", "score_function_squat", "score_function_slr",
        "score_function_sll", "score_function_avg", "score_explosive", "score_explosive_vj",
        "score_explosive_vjr", "score_explosive_vjl", "score_explosive_cvj",
        "score_explosive_dbj", "score_explosive_avg", "score_dysfunction", "score_vulnerability",
        "focus_0_code", "focus_0_name", "focus_0_score",
        "focus_1_code", "focus_1_name", "focus_1_score",
        "focus_2_code", "focus_2_name", "focus_2_score",
        "anklt_vulnerability", "anklt_count", "anklt_mb", "anklt_kn",
        "ankrt_vulnerability", "ankrt_count", "ankrt_mb", "ankrt_kn",
        "knelt_vulnerability", "knelt_count", "knelt_mb", "knelt_allo", "knelt_alla", "knelt_kn",
        "knert_vulnerability", "knert_count", "knert_mb", "knert_allo", "knert_alla", "knert_kn",
        "hiplt_vulnerability", "hiplt_count", "hiplt_mb", "hiplt_kn",
        "hiprt_vulnerability", "hiprt_count", "hiprt_mb", "hiprt_kn",
        "sholt_vulnerability", "sholt_count", "sholt_mb", "sholt_al",
        "short_vulnerability", "short_count", "short_mb", "short_al",
        "spnlo_vulnerability", "spnlo_count", "spnlo_mb", "spnlo_al", "spnlo_sw",
        "spnup_vulnerability", "spnup_count", "spnup_mb", "spnup_al",
        "muscle_hipl", "muscle_hipr", "muscle_kneel", "muscle_kneer",
        "muscle_anklel", "muscle_ankler", "muscle_psoasl", "muscle_psoasr",
        "dp1_left_shoulder_angle_max", "dp1_right_shoulder_angle_max",
        "dp2_left_shoulder_angle_min", "dp2_right_shoulder_angle_min",
        "dp7_jump_height", "dp7_left_hip_takeoff_torque_pct", "dp7_left_knee_takeoff_torque_pct",
        "dp7_left_ankle_takeoff_torque_pct", "dp7_right_hip_takeoff_torque_pct",
        "dp7_right_knee_takeoff_torque_pct", "dp7_right_ankle_takeoff_torque_pct",
        "dp7_grf_max", "dp7_net_impulse", "dp7_rfd",
        "dp9_squat_depth", "dp9_right_hip_flexion", "dp9_right_knee_flexion", "dp9_right_ankle_flexion", "dp9_kne_dyn_val_max_r",
        "dp10_squat_depth", "dp10_left_hip_flexion", "dp10_left_knee_flexion", "dp10_left_ankle_flexion", "dp10_kne_dyn_val_max_l",
        "dp11_jump_height", "dp11_grf_max", "dp11_net_impulse", "dp11_rfd",
        "dp12_jump_height", "dp12_grf_max", "dp12_net_impulse", "dp12_rfd",
        "dp15_left_shoulder_ext", "dp15_right_shoulder_ext", "dp15_left_shoulder_int", "dp15_right_shoulder_int",
        "dp16_left_shoulder_max", "dp16_right_shoulder_max", "dp16_left_shoulder_min", "dp16_right_shoulder_min",
        "dp19_jump_height", "dp19_grf_max", "dp19_net_impulse", "dp19_stance_time",
        "dp45_jump_height", "dp45_grf_max", "dp45_net_impulse", "dp45_rfd",
        "dp151_st_ln_max", "dp152_st_ln_max",
        "dp156_squat_depth", "dp156_left_hip_flexion", "dp156_left_knee_flexion", "dp156_left_ankle_flexion",
        "dp156_right_hip_flexion", "dp156_right_knee_flexion", "dp156_right_ankle_flexion",
        "dp156_pct_diff_max_l", "dp156_pct_diff_max_r",
        "dp157_th_rot_e3", "dp157_lum_rot_e3", "dp158_th_rot_e3", "dp158_lum_rot_e3",
        "dp163_rbalance_lt_xrom", "dp163_rbalance_lt_yrom",
        "dp164_lbalance_lt_xrom", "dp164_lbalance_lt_yrom",
    ],
    "armcare": [
        "master_uid", "armcare_id", "exam_date", "first_name", "last_name",
        "email", "arm_score", "total_strength", "shoulder_balance", "svr",
        "irtarm_strength", "ertarm_strength", "velo",
        "irtarm_rom", "ertarm_rom", "throws", "position_1", "playing_level",
    ],
    "vald_performance": [
        "master_uid", "vald_external_id", "athlete_name", "test_type",
        "test_date", "bw_kg", "jump_height_flight_in", "peak_power_w",
        "rsi_modified", "eccentric_peak_force_n", "concentric_impulse_100ms",
        "jump_height_imp_mom_in", "eccentric_peak_power_per_bm", "bodyweight_lbs",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL env var not set.\n"
            "Export it before running: export DATABASE_URL=postgres://..."
        )
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Create all tables and indexes. Safe to run multiple times."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(SCHEMA)
    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized — all tables ready.")


def _map_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Remap DataFrame columns to canonical DB names using alias matching.
    Returns (remapped_df, warnings).
    Mirrors the _map_columns() approach in pwrx_db.py.
    """
    warnings = []
    col_lower = {c.strip().lower(): c for c in df.columns}
    rename_map = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = canonical
                break
            if alias.strip().lower() in col_lower:
                original = col_lower[alias.strip().lower()]
                rename_map[original] = canonical
                break

    if rename_map:
        mapped = [f"'{k}' -> '{v}'" for k, v in rename_map.items()]
        warnings.append(f"Remapped: {', '.join(mapped)}")

    df = df.rename(columns=rename_map)
    return df, warnings


def _safe_val(val):
    """Convert NaN / NaT / empty string to None for psycopg2."""
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    if isinstance(val, pd.Timestamp) and pd.isna(val):
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    return val


def _link_master_uid(df: pd.DataFrame, table: str, conn) -> pd.DataFrame:
    """
    Try to populate master_uid column. Two-pass approach:
      Pass 1 — match on source-specific ID (dari_id, armcare_id, vald_id, pushpress_id)
      Pass 2 — fall back to full name match for any rows still unlinked

    If master_uid already present in file, leave as-is.
    """
    if "master_uid" in df.columns and df["master_uid"].notna().any():
        return df

    cur = conn.cursor()

    # ── Pass 1: ID-based match ────────────────────────────────────────────────
    id_map = {
        "dari_motion":      "dari_id",
        "armcare":          "armcare_id",
        "vald_performance": "vald_id",
        "pushpress":        "pushpress_id",
    }
    src_col = id_map.get(table)
    if src_col and src_col in df.columns:
        cur.execute(f"SELECT {src_col}, master_uid FROM master_uid WHERE {src_col} IS NOT NULL")
        id_lookup = {row[0]: row[1] for row in cur.fetchall()}
        df["master_uid"] = df[src_col].map(id_lookup)
        linked_id = df["master_uid"].notna().sum()
        print(f"  Pass 1 (ID match): linked {linked_id}/{len(df)} rows via {src_col}")
    else:
        df["master_uid"] = None
        linked_id = 0

    # ── Pass 2: name-based match for anything still unlinked ──────────────────
    unlinked = df["master_uid"].isna().sum()
    if unlinked > 0:
        cur.execute("SELECT LOWER(TRIM(full_name)), master_uid FROM master_uid")
        name_lookup = {row[0]: row[1] for row in cur.fetchall()}

        # Detect which column holds the athlete name in this file
        name_col = next(
            (c for c in ["athlete_name", "full_name", "Name", "name",
                         "first_name", "First Name"] if c in df.columns),
            None
        )
        # For tables with separate first/last name columns, build a combined key
        if name_col is None and "first_name" in df.columns and "last_name" in df.columns:
            combined = (df["first_name"].fillna("") + " " + df["last_name"].fillna("")).str.strip().str.lower()
            mask = df["master_uid"].isna()
            df.loc[mask, "master_uid"] = combined[mask].map(name_lookup)
        elif name_col:
            mask = df["master_uid"].isna()
            df.loc[mask, "master_uid"] = df.loc[mask, name_col].str.strip().str.lower().map(name_lookup)

        linked_name = df["master_uid"].notna().sum() - linked_id
        still_unlinked = df["master_uid"].isna().sum()
        print(f"  Pass 2 (name match): linked {linked_name} more rows")
        if still_unlinked > 0:
            print(f"  WARNING: {still_unlinked} rows could not be linked to a master_uid — will upload without link")

    cur.close()
    return df


# ─────────────────────────────────────────────────────────────────────────────
# INGEST
# ─────────────────────────────────────────────────────────────────────────────

def ingest_file(path: str, table: str, verbose: bool = True) -> dict:
    """
    Load a CSV or XLSX file and insert rows into the specified table.
    Returns dict with inserted, skipped, flagged, warnings.

    Mirrors pwrx_db.ingest_xlsx() pattern.
    """
    init_db()
    warnings = []

    # Read file
    try:
        if path.lower().endswith(".csv"):
            df = pd.read_csv(path, dtype=str)
        else:
            df = pd.read_excel(path, dtype=str)
    except Exception as exc:
        raise ValueError(f"Could not read file: {exc}")

    if df.empty:
        raise ValueError("File is empty")

    # Strip whitespace from all string columns
    df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)

    # Map columns
    df, col_warnings = _map_columns(df)
    warnings.extend(col_warnings)

    cols = TABLE_COLUMNS.get(table)
    if not cols:
        raise ValueError(f"Unknown table: {table}")

    conn = get_conn()

    # Try to auto-link master_uid
    if table != "master_uid":
        df = _link_master_uid(df, table, conn)

    inserted = skipped = flagged = 0
    unique_key = TABLE_UNIQUE_KEY.get(table)
    cur = conn.cursor()

    for _, row in df.iterrows():
        values = [_safe_val(row.get(c)) for c in cols]

        if all(v is None for v in values):
            skipped += 1
            continue

        try:
            placeholders = ", ".join(["%s"] * len(cols))
            col_list = ", ".join(cols)

            if unique_key and unique_key in cols:
                sql = f"""
                    INSERT INTO {table} ({col_list})
                    VALUES ({placeholders})
                    ON CONFLICT ({unique_key}) DO UPDATE
                    SET {', '.join(f"{c}=EXCLUDED.{c}" for c in cols if c != unique_key)}
                """
            else:
                sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

            cur.execute(sql, values)
            inserted += 1

        except Exception as exc:
            skipped += 1
            if verbose:
                print(f"  Row skipped: {exc}")

    conn.commit()
    cur.close()
    conn.close()

    if verbose:
        print(f"Ingest complete -> {inserted} inserted, {skipped} skipped, {flagged} flagged")
        for w in warnings:
            print(f"  {w}")

    return {"inserted": inserted, "skipped": skipped, "flagged": flagged, "warnings": warnings}


# ─────────────────────────────────────────────────────────────────────────────
# ROSTER QUERY
# ─────────────────────────────────────────────────────────────────────────────

def get_roster() -> list[dict]:
    """Return all athletes with session counts per source."""
    conn = get_conn()
    df = pd.read_sql("""
        SELECT
            m.master_uid,
            m.full_name,
            COUNT(DISTINCT d.id)  AS dari_sessions,
            COUNT(DISTINCT v.id)  AS vald_sessions,
            COUNT(DISTINCT a.id)  AS armcare_sessions,
            COUNT(DISTINCT p.id)  AS pushpress_records,
            MAX(d.session_ts)     AS last_dari,
            MAX(v.test_date)      AS last_vald,
            MAX(a.exam_date)      AS last_armcare
        FROM master_uid m
        LEFT JOIN dari_motion     d ON d.master_uid = m.master_uid
        LEFT JOIN vald_performance v ON v.master_uid = m.master_uid
        LEFT JOIN armcare          a ON a.master_uid = m.master_uid
        LEFT JOIN pushpress        p ON p.master_uid = m.master_uid
        GROUP BY m.master_uid, m.full_name
        ORDER BY m.full_name
    """, conn)
    conn.close()
    return df.to_dict("records")


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADER FOR REPORT  (called by generate_sc_report.py and main.py)
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_label(date_val) -> str:
    """Convert date/timestamp to 'Jan '26' label."""
    try:
        if isinstance(date_val, str):
            date_val = pd.to_datetime(date_val)
        return date_val.strftime("%b '%y")
    except Exception:
        return str(date_val)[:7]


def _safe_float(val, default=0.0) -> float:
    try:
        f = float(val)
        return default if (f != f) else f   # NaN check
    except (TypeError, ValueError):
        return default


def load_athlete_data(athlete_name: str) -> dict:
    """
    Fetch last 4 sessions per source for an athlete and return
    a DATA dict compatible with generate_sc_report.render_report().
    """
    conn = get_conn()

    # ── Resolve master_uid ──────────────────────────────────────────────────
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT master_uid, full_name
        FROM master_uid
        WHERE full_name ILIKE %s
           OR (first_name || ' ' || last_name) ILIKE %s
        LIMIT 1
    """, (f"%{athlete_name}%", f"%{athlete_name}%"))
    athlete = cur.fetchone()
    if not athlete:
        raise ValueError(f"Athlete not found: {athlete_name}")
    uid  = athlete["master_uid"]
    name = athlete["full_name"]

    # ── Dari ────────────────────────────────────────────────────────────────
    cur.execute("""
        SELECT session_ts, score_overall, score_function, score_explosive,
               score_dysfunction, score_vulnerability,
               focus_0_name, focus_1_name, focus_2_name
        FROM dari_motion
        WHERE master_uid = %s AND session_ts IS NOT NULL
        ORDER BY session_ts DESC LIMIT %s
    """, (uid, MAX_SESSIONS))
    dari_rows = list(reversed(cur.fetchall()))

    # ── Vald ────────────────────────────────────────────────────────────────
    cur.execute("""
        SELECT test_date, jump_height_flight_in, peak_power_w,
               rsi_modified, eccentric_peak_force_n, bodyweight_lbs
        FROM vald_performance
        WHERE master_uid = %s AND test_date IS NOT NULL
        ORDER BY test_date DESC LIMIT %s
    """, (uid, MAX_SESSIONS))
    vald_rows = list(reversed(cur.fetchall()))

    # ── ArmCare ─────────────────────────────────────────────────────────────
    cur.execute("""
        SELECT exam_date, arm_score, total_strength,
               shoulder_balance, svr, irtarm_strength, ertarm_strength, velo
        FROM armcare
        WHERE master_uid = %s AND exam_date IS NOT NULL
        ORDER BY exam_date DESC LIMIT %s
    """, (uid, MAX_SESSIONS))
    arm_rows = list(reversed(cur.fetchall()))

    cur.close()
    conn.close()

    # ── Map to DATA dict shape ───────────────────────────────────────────────
    def _dari_trend(rows):
        return [{"session":       _fmt_label(r["session_ts"]),
                 "athleticism":   _safe_float(r["score_overall"]),
                 "functionality": _safe_float(r["score_function"]),
                 "explosiveness": _safe_float(r["score_explosive"]),
                 "dysfunction":   _safe_float(r["score_dysfunction"])} for r in rows]

    def _vald_trend(rows):
        return [{"session":     _fmt_label(r["test_date"]),
                 "jump_height": round(_safe_float(r["jump_height_flight_in"]), 2),
                 "peak_power":  int(_safe_float(r["peak_power_w"])),
                 "rsi_mod":     round(_safe_float(r["rsi_modified"]), 3)} for r in rows]

    def _arm_trend(rows):
        return [{"session":        _fmt_label(r["exam_date"]),
                 "arm_score":      round(_safe_float(r["arm_score"]), 1),
                 "total_strength": round(_safe_float(r["total_strength"]), 1),
                 "balance":        round(_safe_float(r["shoulder_balance"]), 2),
                 "svr":            round(_safe_float(r["svr"]), 2)} for r in rows]

    empty_dari = {"session": "N/A", "athleticism": 0, "functionality": 0,
                  "explosiveness": 0, "dysfunction": 0}
    empty_vald = {"session": "N/A", "jump_height": 0, "peak_power": 0, "rsi_mod": 0}
    empty_arm  = {"session": "N/A", "arm_score": 0, "total_strength": 0,
                  "balance": 1.0, "svr": 0}

    dari_trend = _dari_trend(dari_rows) if dari_rows else [empty_dari]
    vald_trend = _vald_trend(vald_rows) if vald_rows else [empty_vald]
    arm_trend  = _arm_trend(arm_rows)  if arm_rows  else [empty_arm]

    last_dari = dari_rows[-1] if dari_rows else {}
    focus_areas = [f for f in [
        last_dari.get("focus_0_name"),
        last_dari.get("focus_1_name"),
        last_dari.get("focus_2_name"),
    ] if f] or ["No focus areas recorded"]

    return {
        "athlete_name": name,
        "master_uid":   uid,
        "report_date":  datetime.datetime.now().strftime("%b %Y"),
        "dari": {
            "trend":   dari_trend,
            "current": dari_trend[-1],
            "percentiles": {
                "athleticism":   dari_trend[-1]["athleticism"],
                "explosiveness": dari_trend[-1]["explosiveness"],
                "dysfunction":   dari_trend[-1]["dysfunction"],
                "vulnerability": _safe_float(last_dari.get("score_vulnerability")),
            },
            "focus_areas": focus_areas,
        },
        "vald": {
            "trend":   vald_trend,
            "current": vald_trend[-1],
            "prev":    vald_trend[-2] if len(vald_trend) >= 2 else vald_trend[-1],
        },
        "arm": {
            "trend":   arm_trend,
            "current": arm_trend[-1],
            "prev":    arm_trend[-2] if len(arm_trend) >= 2 else arm_trend[-1],
        },
        "inbody": {
            "weight": 0, "smm": 0, "pbf": 0, "bmi": 0, "score": 0,
            "segments": [{"segment": s, "lean_mass": 0, "highlight": False}
                         for s in ["R Arm", "L Arm", "Trunk", "R Leg", "L Leg"]],
        },
        "data_coverage": {
            "dari":    len(dari_rows),
            "vald":    len(vald_rows),
            "armcare": len(arm_rows),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PWRX S&C Database Layer")
    parser.add_argument("file",       nargs="?",          help="CSV or XLSX file to ingest")
    parser.add_argument("--table",    default=None,       help="Target table: master_uid | pushpress | dari_motion | armcare | vald_performance")
    parser.add_argument("--init",     action="store_true",help="Create all tables and exit")
    parser.add_argument("--roster",   action="store_true",help="Print roster summary")
    parser.add_argument("--athlete",  default=None,       help="Print session counts for one athlete")
    args = parser.parse_args()

    if args.init:
        init_db()
        sys.exit(0)

    if args.roster:
        rows = get_roster()
        print(f"{'Athlete':<30} {'Dari':>5} {'Vald':>5} {'Arm':>5} {'PP':>5}")
        print("-" * 50)
        for r in rows:
            print(f"{r['full_name']:<30} {r['dari_sessions']:>5} {r['vald_sessions']:>5} {r['armcare_sessions']:>5} {r['pushpress_records']:>5}")
        print(f"\n{len(rows)} athletes total")
        sys.exit(0)

    if args.athlete:
        data = load_athlete_data(args.athlete)
        cov  = data["data_coverage"]
        print(f"\nData coverage for: {data['athlete_name']}")
        print(f"  Dari sessions:    {cov['dari']}")
        print(f"  Vald sessions:    {cov['vald']}")
        print(f"  ArmCare sessions: {cov['armcare']}")
        sys.exit(0)

    if args.file:
        if not args.table:
            parser.error("--table is required when ingesting a file")
        result = ingest_file(args.file, args.table, verbose=True)
        print(f"inserted={result['inserted']}, skipped={result['skipped']}, flagged={result['flagged']}")
        for w in result["warnings"]:
            print(f"  {w}")
    else:
        parser.print_help()
