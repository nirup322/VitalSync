# VitalSync 🫀

**VitalSync** is a real-time ICU patient vitals monitoring dashboard built with Streamlit, powered by an ESP32 microcontroller connected to an AD8232 ECG sensor and an MQ air-quality sensor. It supports both a simulated demo mode (Faker Simulation) and live hardware mode (Hardware Serial) for real-time patient monitoring.

---

## Features

- 📡 **Dual data modes** — switch between Faker Simulation (for demos) and Hardware Serial (live ESP32 data)
- 🫀 **Live ECG waveform** streamed from the AD8232 sensor
- ❤️ **Real-time Heart Rate (BPM)** tracking with rolling average
- 🌬️ **Air Quality monitoring** via MQ gas sensor
- 👤 **Patient profile management** — name, age, ward, and bed assignment
- ⚠️ **Threshold-based alerts** — flags abnormal readings and disconnected ECG leads
- 📁 **Session history** — logs and stores past monitoring sessions
- 🔌 **Auto COM port detection** for hardware connection

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend / Dashboard | Streamlit (Python) |
| Hardware | ESP32, AD8232 ECG Sensor, MQ Air Quality Sensor |
| Firmware | Arduino (`.ino`) |
| Data Visualization | Plotly |
| Hosting | Render |

---

## Documentation

| Doc | Covers |
|---|---|
| [Hardware Setup](#hardware-setup) | Wiring, sensor connections, ESP32 firmware upload |
| [Running Locally](#running-locally) | Local setup for Faker Simulation and Hardware Serial modes |
| [Deployment](#deployment) | Hosting the dashboard on Render |

### Hardware Setup

The ESP32 is flashed with `multisensor_health_monitoring_firebase.ino`, which reads:
- **AD8232** — ECG waveform and lead-on/off detection
- **MQ sensor** — air quality readings

Sensor data is sent over **Serial (115200 baud)** to the connected computer running the dashboard.

### Running Locally

```bash
git clone https://github.com/nirup322/VitalSync.git
cd VitalSync
pip install -r requirements.txt
streamlit run app.py
```

In the sidebar, choose a **Mode**:
- **Faker Simulation** — generates synthetic vitals for demo/testing
- **Hardware Serial** — select the correct COM port and baud rate (115200) to read live data from the ESP32

> ⚠️ Hardware Serial mode requires the dashboard to run **locally** on the same machine the ESP32 is physically connected to — cloud-hosted instances (like Render) cannot access a local USB/COM port.

### Deployment

The dashboard is deployed on **Render** as a Python web service:
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

---

## Links

| Resource | Link |
|---|---|
| Live App  | [vitalsync-3h24.onrender.com](https://vitalsync-3h24.onrender.com) |
| Source Code | [github.com/nirup322/VitalSync](https://github.com/nirup322/VitalSync) |
| Firmware (ESP32) | [multisensor_health_monitoring_firebase.ino](https://github.com/nirup322/VitalSync/blob/main/multisensor_health_monitoring_firebase.ino) |
| License | [MIT License](https://github.com/nirup322/VitalSync/blob/main/LICENSE) |
| Author | [@nirup322](https://github.com/nirup322) |

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
