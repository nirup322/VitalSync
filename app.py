import math
import random
import re
import time
from collections import deque
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import serial
import serial.tools.list_ports
import streamlit as st
from faker import Faker

# Initialize Faker
fake = Faker()

# ============================================================
# CONFIG
# ============================================================
BAUD_RATE_DEFAULT = 115200
READ_TIMEOUT = 0.5
TABLE_WINDOW_MIN = 5
MQ_ALERT = 800
BPM_MAX = 130
BPM_MIN = 50
UI_UPDATE_INTERVAL = 0.8 

# Regex to match your ESP32 Serial output
LINE_PATTERN = re.compile(
    r"ECG:\s*(-?\d+)\s*\|\s*LO\+:\s*(\d+)\s*\|\s*LO-:\s*(\d+)\s*\|\s*"
    r"MQ:\s*(\d+)\s*\|\s*IR:\s*(-?\d+)\s*\|\s*RED:\s*(-?\d+)\s*\|\s*"
    r"BPM:\s*(-?\d+\.?\d*)\s*\|\s*AVG BPM:\s*(-?\d+)"
)

COL_BG, COL_CARD, COL_BORDER, COL_TEXT = "#0B0F14", "#121821", "#212A36", "#E7ECF2"
COL_MUTED, COL_ACCENT, COL_GOOD, COL_WARN, COL_BAD = "#8A97A8", "#4F8CFF", "#2ECC8F", "#FFB020", "#FF5C5C"

# ============================================================
# PAGE SETUP
# ============================================================
st.set_page_config(page_title="VitalSyunc | Live Dashboard", layout="wide", page_icon="🩺")

st.markdown(f"""
<style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stApp {{ background: {COL_BG}; color: {COL_TEXT}; font-family: 'Inter', sans-serif; }}
    .vg-header {{ display:flex; align-items:center; justify-content:space-between; padding: 18px 26px; border-radius: 16px; margin-bottom: 22px; background: rgba(79,140,255,0.1); border: 1px solid {COL_BORDER}; }}
    .vg-card {{ background: {COL_CARD}; border: 1px solid {COL_BORDER}; border-radius: 14px; padding: 16px 18px; height: 100%; }}
    .vg-card .lbl {{ color: {COL_MUTED}; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
    .vg-card .val {{ font-size: 26px; font-weight: 800; margin-top: 4px; }}
    .vg-good {{ color: {COL_GOOD}; }} .vg-warn {{ color: {COL_WARN}; }} .vg-bad {{ color: {COL_BAD}; }}
    .chart-title {{ font-size: 14px; font-weight: 600; color: {COL_MUTED}; margin-bottom: 8px; margin-top: 15px; }}
    .patient-box {{ background: rgba(79,140,255,0.05); padding: 15px; border-radius: 10px; border: 1px dashed {COL_BORDER}; margin-bottom: 20px; }}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HELPERS
# ============================================================
def find_arduino_ports():
    all_ports = list(serial.tools.list_ports.comports())
    return [p.device for p in all_ports if any(kw in (p.description or "").lower() for kw in ["arduino", "usb", "uart", "cp210", "ch340", "espressif"])]

def get_new_patient(name=None):
    return {
        "name": name.strip() if name and name.strip() else fake.name(),
        "age": random.randint(18, 85),
        "id": fake.uuid4()[:8].upper(),
        "location": f"Ward {random.randint(1, 10)}, Bed {random.randint(1, 20)}",
        "condition": "Stable"
    }
def sim_step_faker(state, now):
    dt = 0.05
    if now > state["event_end"]:
        state["current_scenario"] = random.choices(["Normal", "Tachycardia", "Air Hazard", "Leads Off"], weights=[0.7, 0.1, 0.1, 0.1])[0]
        state["event_end"] = now + random.uniform(5, 10)
    
    target_bpm = {"Normal": 72.0, "Tachycardia": 145.0, "Air Hazard": 85.0, "Leads Off": 0.0}[state["current_scenario"]]
    target_mq = 950.0 if state["current_scenario"] == "Air Hazard" else 350.0
    leads_off = state["current_scenario"] == "Leads Off"

    state["bpm"] += (target_bpm - state["bpm"]) * 0.1
    state["mq"] += (target_mq - state["mq"]) * 0.05 + random.uniform(-2, 2)
    state["beat_phase"] += dt * (state["bpm"] / 60.0)
    phase = state["beat_phase"] % 1.0
    ecg = (1650 + (1200 * math.exp(-pow(phase-0.15, 2)/0.0005)) + random.randint(-15, 15)) if not leads_off else random.randint(0, 100)

    return {"ecg": float(ecg), "lo_plus": "1" if leads_off else "0", "mq": state["mq"], "bpm": state["bpm"], "avg_bpm": state["bpm"], "scenario": state["current_scenario"]}

def create_sensor_fig(df, y_col, label, color, height=220):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["time"], y=df[y_col], name=label, line=dict(color=color, width=2), fill='tozeroy', fillcolor="rgba(100,100,100,0.05)"))
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=10, r=10, t=5, b=5), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=COL_BORDER))
    return fig

# ============================================================
# STATE
# ============================================================
if "raw" not in st.session_state:
    st.session_state.raw = deque(maxlen=400)
    st.session_state.full_log = []
    st.session_state.patient = get_new_patient()
    st.session_state.sim_state = {"bpm": 72.0, "mq": 350.0, "beat_phase": 0.0, "event_end": 0, "current_scenario": "Normal"}

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("⚙️ Connection")
    mode = st.radio("Mode", ["Faker Simulation", "Hardware Serial"])
    
    selected_port = None
    baud_rate = BAUD_RATE_DEFAULT
    
    if mode == "Hardware Serial":
        ports = find_arduino_ports()
        selected_port = st.selectbox("Select COM Port", ports if ports else ["No Ports Found"])
        baud_rate = st.number_input("Baud Rate", value=BAUD_RATE_DEFAULT)
        if not ports:
            st.warning("🔌 No ESP32 detected. Check USB cable.")

    st.divider()
    if st.button("🔄 New Patient Profile"):
        st.session_state.patient = get_new_patient()
        st.session_state.raw.clear()
        st.session_state.full_log = []

    run = st.toggle("▶️ Stream Data", value=False)
    
    st.divider()
    st.caption(f"ID: {st.session_state.patient['id']}")
    st.caption(f"Name: {st.session_state.patient['name']}")

# ============================================================
# UI LAYOUT
# ============================================================
st.markdown(f'<div class="vg-header"><div><p style="font-size:24px; font-weight:800; margin:0;">🩺 VitalGrid Analytics</p></div><div style="color:{COL_GOOD if run else COL_MUTED}">● {mode}</div></div>', unsafe_allow_html=True)

tab_live, tab_history = st.tabs(["📊 Live Monitoring", "📁 Session History"])

with tab_live:
    p = st.session_state.patient
    st.markdown(f'<div class="patient-box"><span style="color:{COL_ACCENT}; font-weight:bold;">PATIENT:</span> {p["name"]} ({p["age"]}y) &nbsp;|&nbsp; <span style="color:{COL_ACCENT}; font-weight:bold;">LOC:</span> {p["location"]} &nbsp;|&nbsp; <span style="color:{COL_ACCENT}; font-weight:bold;">STATUS:</span> {p["condition"]}</div>', unsafe_allow_html=True)
    
    alert_ph = st.empty()
    c1, c2, c3, c4 = st.columns(4)
    bpm_ph, avg_ph, mq_ph, ecg_stat_ph = c1.empty(), c2.empty(), c3.empty(), c4.empty()

    st.markdown('<p class="chart-title">ECG WAVEFORM (AD8232)</p>', unsafe_allow_html=True)
    ecg_chart_ph = st.empty()
    g1, g2 = st.columns(2)
    with g1:
        st.markdown('<p class="chart-title">HEART RATE (BPM)</p>', unsafe_allow_html=True)
        bpm_chart_ph = st.empty()
    with g2:
        st.markdown('<p class="chart-title">AIR QUALITY (MQ)</p>', unsafe_allow_html=True)
        mq_chart_ph = st.empty()

# ============================================================
# MAIN LOOP
# ============================================================
if run:
    ser = None
    if mode == "Hardware Serial":
        if not selected_port or selected_port == "No Ports Found":
            st.error("Please select a valid COM port.")
            st.stop()
        try:
            ser = serial.Serial(selected_port, baud_rate, timeout=READ_TIMEOUT)
            time.sleep(2) # Wait for ESP32 reboot
        except Exception as e:
            st.error(f"Failed to connect to {selected_port}: {e}")
            st.stop()

    last_ui_update = 0
    while run:
        now = time.time()
        parsed = None

        if mode == "Faker Simulation":
            parsed = sim_step_faker(st.session_state.sim_state, now)
            time.sleep(0.05)
        else:
            try:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    match = LINE_PATTERN.search(line)
                    if match:
                        ecg, lo_plus, lo_minus, mq, ir, red, bpm, avg_bpm = match.groups()
                        parsed = {
                            "ecg": float(ecg), "lo_plus": lo_plus, "mq": float(mq),
                            "bpm": float(bpm), "avg_bpm": float(avg_bpm), "scenario": "Hardware Live"
                        }
            except Exception as e:
                st.error(f"Serial Error: {e}")
                break

        if parsed:
            parsed['t'] = now
            st.session_state.raw.append(parsed)
            st.session_state.full_log.append(parsed)

            # Metrics
            style = '<div class="vg-card"><div class="lbl">{}</div><div class="val {}">{}</div></div>'
            b_val, mq_val, lo = parsed['bpm'], parsed['mq'], parsed['lo_plus'] == '1'
            
            bpm_ph.markdown(style.format("Heart Rate", "bad" if (b_val > BPM_MAX or (b_val < BPM_MIN and b_val > 0)) else "good", f"{b_val:.1f}"), unsafe_allow_html=True)
            avg_ph.markdown(style.format("Avg BPM", "", f"{parsed['avg_bpm']:.0f}"), unsafe_allow_html=True)
            mq_ph.markdown(style.format("Air Quality", "bad" if mq_val > MQ_ALERT else "good", f"{mq_val:.0f}"), unsafe_allow_html=True)
            ecg_stat_ph.markdown(style.format("Leads", "bad" if lo else "good", "OFF" if lo else "OK"), unsafe_allow_html=True)

            # Alerts
            if lo: alert_ph.error(f"🚨 Patient {p['name']} ECG Leads Disconnected!")
            elif b_val > BPM_MAX: alert_ph.error(f"🚨 Tachycardia Alert for {p['name']}! BPM: {b_val:.1f}")
            elif mq_val > MQ_ALERT: alert_ph.warning(f"⚠️ Air Quality Hazard detected near {p['name']}!")
            else: alert_ph.success(f"✅ Monitoring {p['name']}: {parsed['scenario']}")

            # Throttled Charts
            if now - last_ui_update > UI_UPDATE_INTERVAL:
                df = pd.DataFrame(list(st.session_state.raw))
                df["time"] = pd.to_datetime(df["t"], unit='s')
                ecg_chart_ph.plotly_chart(create_sensor_fig(df, "ecg", "ECG", COL_ACCENT, height=250), use_container_width=True)
                bpm_chart_ph.plotly_chart(create_sensor_fig(df, "bpm", "BPM", COL_GOOD), use_container_width=True)
                mq_chart_ph.plotly_chart(create_sensor_fig(df, "mq", "MQ", COL_WARN), use_container_width=True)
                last_ui_update = now

    if ser: ser.close()
