# 🏥 IoT HealthGuard: Remote Patient Monitoring System
**Showcased at Hackspectra | Project for NLPC 2026 (National Level)**
<img width="1918" height="1026" alt="Screenshot 2026-04-14 195904" src="https://github.com/user-attachments/assets/d40cf193-45f8-4712-8d4c-a2875798f216" />

## 🌟 Executive Summary
IoT HealthGuard is a smart healthcare ecosystem designed to address the "Monitoring Gap" in rural areas.
By utilizing low-cost sensors and high-speed IoT connectivity, the system enables continuous vital sign tracking (Heart Rate & Temperature) with **95% accuracy**.
The project features a robust multi-role dashboard allowing Doctors, Patients, and Vendors to collaborate on a single secure platform.

## 🏆 Recognitions
* **Hackspectra:** Successfully presented and showcased the functional prototype.
* **NLPC 2026:** Selected for the National Level Project Competition (Open Innovation Theme).
![full display](https://github.com/user-attachments/assets/42c84c9f-c54b-43d8-bfa8-91b8dd5969ca)

---

## 👥 Team Members
* **Suleman Shaikh** - Lead Developer & Electronics Integration
* **Santosh Puri** - Hardware Design & Testing
* **Rohan Wankhede** - UI/UX Design & Frontend Development
* **Sanchit Parchandekar** - System Architecture & Documentation

---

## 🚀 Key Features
* **Real-Time Vitals Tracking:** Live BPM and Temperature data transmission via ESP8266.
* **Multi-User Ecosystem:**
    * **👨‍⚕️ Doctor Portal:** A centralized interface for medical professionals to monitor multiple patients, analyze trends, and provide remote consultations.
    * **🩺 Specialist Portal:** Deep-dive analysis tools for specialized cardiovascular or fever tracking.
    * **👤 Patient Portal:** Personal access to health history, live vitals, and emergency contact tools.
    * **📦 Vendor Portal:** Streamlined integration for managing medical supplies and equipment logistics.
* **Instant Emergency Alerts:** Automated visual and system triggers when vitals exceed safe thresholds (e.g., BPM > 100 or Temp > 38°C).
* **Lightweight Data Logging:** Optimized JSON-based database for high-speed performance in low-bandwidth rural areas.

---

## 🛠️ Technical Stack

### **Hardware Components**
- **Microcontroller:** ESP8266 (NodeMCU) for WiFi connectivity.
- **Pulse Sensor:** For Heart Rate (BPM) monitoring.
- **DHT11 Sensor:** For Temperature and Humidity tracking.

### **Software Frameworks**
- **Backend:** Flask (Python 3.x)
- **Frontend:** HTML5, CSS3, JavaScript (AJAX for live updates)
- **Visualization:** Chart.js for real-time graphical representation.

---

## 📁 Project Structure
```text
├── app.py              # Main Flask Backend Server
├── patients.json       # Database for patient records
├── esp8266.ino         # ESP8266 Firmware (Arduino)
├── templates/          # Portal Files: doctor_dashboard.html, patient_dashboard.html, etc.
