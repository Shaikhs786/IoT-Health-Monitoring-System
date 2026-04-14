from flask import Flask, request, session, redirect, render_template, jsonify
import json, os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'health-monitor-2024'

PATIENTS_FILE = 'patients.json'

DEFAULT_PATIENT = {
    "name": "Rohan",
    "age": 20,
    "photo": "https://via.placeholder.com/150/4F46E5/FFFFFF?text=R",
    "current_temp": 36.5,
    "current_bpm": 72,
    "current_spo2": 98,
    "current_rr": 16,
    "current_sugar_fasting": 90,
    "current_sugar_pp": 120,
    "records": [],
    "appointments": [],
    "prescriptions": [
        {"name": "Paracetamol 500mg", "dose": "1 tablet", "timing": "Twice daily after meals", "status": "Active"}
    ],
    "diet": [
        {"item": "Fruits & Vegetables", "note": "Include in every meal"},
        {"item": "Avoid oily food", "note": "Strictly for 2 weeks"}
    ],
    "tests": [
        {"name": "Blood Test", "date": "2024-04-15", "note": "Fasting required"}
    ],
    "health_status": "Stable"
}

# ── SMS Alert config (Twilio) ──────────────────────────────
TWILIO_SID   = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_FROM", "")

# Doctor & Guardian numbers stored in a file so doctor can update from dashboard
ALERT_FILE = 'alert_config.json'

def load_alert_config():
    if os.path.exists(ALERT_FILE):
        try:
            with open(ALERT_FILE) as f:
                return json.load(f)
        except: pass
    return {"doctor_phone": "", "guardian_phone": ""}

def save_alert_config(cfg):
    with open(ALERT_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

alert_config = load_alert_config()
_last_alert_time = None
_manual_override_until = None

def send_sms_alert(patient_name, temp, bpm):
    global _last_alert_time, alert_config
    alert_config = load_alert_config()
    doctor_phone   = alert_config.get('doctor_phone', '')
    guardian_phone = alert_config.get('guardian_phone', '')

    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and "YOUR" not in TWILIO_SID):
        print("⚠️ Twilio not configured — skipping SMS")
        return
    if not doctor_phone and not guardian_phone:
        print("⚠️ No phone numbers configured")
        return

    now = datetime.now()
    if _last_alert_time and (now - _last_alert_time).total_seconds() < 300:
        print("⏳ SMS cooldown active — skipping")
        return

    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)

        doctor_msg = (
            f"🚨 CRITICAL ALERT - Smart Health Monitor\n"
            f"Patient: {patient_name}\n"
            f"Temp: {temp}°C | BPM: {bpm}\n"
            f"⚠️ Immediate medical attention required!\n"
            f"Time: {now.strftime('%H:%M:%S')}"
        )
        guardian_msg = (
            f"🚨 Health Alert - {patient_name}\n"
            f"Your family member's vitals are CRITICAL.\n"
            f"Temp: {temp}°C | BPM: {bpm}\n"
            f"Please contact the hospital immediately.\n"
            f"Time: {now.strftime('%H:%M:%S')}"
        )

        for num, msg in [(doctor_phone, doctor_msg), (guardian_phone, guardian_msg)]:
            if num.strip():
                client.messages.create(body=msg, from_=TWILIO_FROM, to=num.strip())
                print(f"✅ SMS sent to {num}")

        _last_alert_time = now
    except Exception as e:
        print(f"❌ SMS error: {e}")

# ── Disease prediction ─────────────────────────────────────
def predict_disease(temp, bpm, spo2=98, rr=16):
    conditions = []
    prevention = []

    if temp > 32.4:
        conditions.append("High Fever")
        prevention.append("Take paracetamol, rest, drink fluids")
    elif temp > 30.0:
        conditions.append("Mild Fever")
        prevention.append("Rest and stay hydrated")
    elif temp < 27.2:
        conditions.append("Hypothermia")
        prevention.append("Warm the patient immediately")

    if bpm > 90:
        conditions.append("Tachycardia (High Heart Rate)")
        prevention.append("Avoid caffeine, rest, consult doctor")
    elif bpm < 70:
        conditions.append("Bradycardia (Low Heart Rate)")
        prevention.append("Consult cardiologist immediately")

    if spo2 < 90:
        conditions.append("Severe Hypoxia (Low Oxygen)")
        prevention.append("Administer oxygen immediately")
    elif spo2 < 95:
        conditions.append("Mild Hypoxia")
        prevention.append("Monitor breathing, consult doctor")

    if rr > 20:
        conditions.append("Tachypnea (High Breathing Rate)")
        prevention.append("Check for respiratory infection")
    elif rr < 12:
        conditions.append("Bradypnea (Low Breathing Rate)")
        prevention.append("Seek emergency care")

    if not conditions:
        conditions.append("All Vitals Normal")
        prevention.append("Maintain healthy lifestyle and regular checkups")

    return conditions, prevention

# ── 5-minute interval data for graphs ─────────────────────
def get_hourly_data(records):
    from collections import defaultdict
    bucket_temp = defaultdict(list)
    bucket_bpm  = defaultdict(list)
    for r in records:
        try:
            dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
            # round down to nearest 5 min
            minute = (dt.minute // 5) * 5
            key = dt.strftime("%H:") + f"{minute:02d}"
            bucket_temp[key].append(r['temp'])
            bucket_bpm[key].append(r['bpm'])
        except: pass
    labels, temps, bpms = [], [], []
    for key in sorted(bucket_temp.keys())[-12:]:
        labels.append(key)
        temps.append(round(sum(bucket_temp[key]) / len(bucket_temp[key]), 1))
        bpms.append(round(sum(bucket_bpm[key])  / len(bucket_bpm[key])))
    return labels, temps, bpms

# ── Load patients ──────────────────────────────────────────
def load_patients():
    if os.path.exists(PATIENTS_FILE):
        try:
            with open(PATIENTS_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict): return data
        except: pass
    default_data = {DEFAULT_PATIENT["name"]: DEFAULT_PATIENT}
    save_patients(default_data)
    return default_data

def save_patients(p):
    with open(PATIENTS_FILE, 'w') as f:
        json.dump(p, f, indent=2)

patients = load_patients()

# Force first patient to Rohan
_first_key = list(patients.keys())[0]
if patients[_first_key]['name'] != 'Rohan':
    patients['Rohan'] = patients.pop(_first_key)
    patients['Rohan']['name'] = 'Rohan'
    patients['Rohan']['age'] = 20
    save_patients(patients)

# ── ESP8266 data receiver ──────────────────────────────────
@app.route('/data', methods=['GET'])
def receive_data():
    global _manual_override_until
    temp = request.args.get('temp')
    bpm  = request.args.get('bpm')
    spo2 = request.args.get('spo2', 98)
    rr   = request.args.get('rr', 16)
    print(f"📡 LIVE: Temp={temp}°C BPM={bpm} SpO2={spo2} RR={rr}")

    # If doctor manually added data, block sensor override for 60 sec
    if _manual_override_until and datetime.now().timestamp() < _manual_override_until:
        print("⏳ Manual override active — ignoring sensor data")
        return "Data Received"

    if temp and bpm:
        try:
            p = list(patients.values())[0]
            p['current_temp'] = float(temp)
            p['current_bpm']  = int(bpm)
            p['current_spo2'] = int(spo2)
            p['current_rr']   = int(rr)
            record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "temp": float(temp), "bpm": int(bpm),
                "spo2": int(spo2),   "rr": int(rr)
            }
            p['records'].append(record)
            p['records'] = p['records'][-200:]
            save_patients(patients)
            # SMS alert on critical
            if float(temp) > 32.4 or int(bpm) > 90 or int(bpm) < 70:
                send_sms_alert(p['name'], temp, bpm)
        except Exception as e:
            print(e)
    return "Data Received"

# ── Live data API for AJAX update ─────────────────────────
@app.route('/api/live')
def api_live():
    p = list(patients.values())[0]
    return jsonify({
        'temp':  p['current_temp'],
        'bpm':   p['current_bpm'],
        'spo2':  p.get('current_spo2', 98),
        'rr':    p.get('current_rr', 16),
        'records': p['records'][-20:]
    })

# ── Home Landing Page ──────────────────────────────────────
@app.route('/home')
def home():
    return render_template('home.html')

# ── Doctor Login ───────────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        patient_name = request.form.get('username', '').strip()
        password     = request.form.get('password', '')
        if password == 'Appollo@':
            if patient_name not in patients:
                patients[patient_name] = DEFAULT_PATIENT.copy()
                patients[patient_name]['name'] = patient_name
                save_patients(patients)
            session['patient_name'] = patient_name
            return redirect('/dashboard')
        else:
            error = 'Invalid credentials. Please try again.'
    return render_template('login.html', error=error)

# ── Doctor Dashboard ───────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'patient_name' not in session:
        return redirect('/')
    p = list(patients.values())[0]
    last_record = p['records'][-1] if p['records'] else None
    conditions, prevention = predict_disease(
        p['current_temp'], p['current_bpm'],
        p.get('current_spo2', 98), p.get('current_rr', 16)
    )
    labels, h_temps, h_bpms = get_hourly_data(p['records'])
    return render_template('dashboard.html', patient=p, last_record=last_record,
                           conditions=conditions, prevention=prevention,
                           h_labels=labels, h_temps=h_temps, h_bpms=h_bpms,
                           alert_config=load_alert_config())

# ── Doctor Manual Data Entry ───────────────────────────────
@app.route('/add-data', methods=['POST'])
def add_data():
    global _manual_override_until
    if 'patient_name' not in session:
        return redirect('/')
    try:
        temp    = float(request.form.get('temp'))
        bpm     = int(request.form.get('bpm'))
        spo2    = int(request.form.get('spo2', 98))
        rr      = int(request.form.get('rr', 16))
        sugar_f = float(request.form.get('sugar_fasting') or 0)
        sugar_p = float(request.form.get('sugar_pp') or 0)
        p = list(patients.values())[0]
        p['current_temp'] = temp
        p['current_bpm']  = bpm
        p['current_spo2'] = spo2
        p['current_rr']   = rr
        if sugar_f: p['current_sugar_fasting'] = sugar_f
        if sugar_p: p['current_sugar_pp']      = sugar_p
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "temp": temp, "bpm": bpm, "spo2": spo2, "rr": rr,
            "sugar_fasting": sugar_f, "sugar_pp": sugar_p
        }
        p['records'].append(record)
        p['records'] = p['records'][-200:]
        save_patients(patients)
        _manual_override_until = datetime.now().timestamp() + 60
    except Exception as e:
        print(e)
    return redirect('/dashboard')

# ── History ────────────────────────────────────────────────
@app.route('/history')
def history():
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    return render_template('history.html', patient=p)

@app.route('/logout')
def logout():
    session.pop('patient_name', None)
    return redirect('/')

# ── Save alert phone numbers ───────────────────────────────
@app.route('/save-alert-config', methods=['POST'])
def save_alert_config_route():
    if 'patient_name' not in session: return redirect('/')
    cfg = {
        "doctor_phone":   request.form.get('doctor_phone', '').strip(),
        "guardian_phone": request.form.get('guardian_phone', '').strip()
    }
    save_alert_config(cfg)
    return redirect('/dashboard')

# ── Doctor: Add Prescription ───────────────────────────────
@app.route('/add-prescription', methods=['POST'])
def add_prescription():
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'prescriptions' not in p: p['prescriptions'] = []
    p['prescriptions'].append({
        "name":   request.form.get('med_name', '').strip(),
        "dose":   request.form.get('med_dose', '').strip(),
        "timing": request.form.get('med_timing', '').strip(),
        "status": "Active"
    })
    save_patients(patients)
    return redirect('/dashboard')

@app.route('/delete-prescription/<int:idx>', methods=['POST'])
def delete_prescription(idx):
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'prescriptions' in p and 0 <= idx < len(p['prescriptions']):
        p['prescriptions'].pop(idx)
        save_patients(patients)
    return redirect('/dashboard')

# ── Doctor: Add Diet ───────────────────────────────────────
@app.route('/add-diet', methods=['POST'])
def add_diet():
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'diet' not in p: p['diet'] = []
    p['diet'].append({
        "item": request.form.get('diet_item', '').strip(),
        "note": request.form.get('diet_note', '').strip()
    })
    save_patients(patients)
    return redirect('/dashboard')

@app.route('/delete-diet/<int:idx>', methods=['POST'])
def delete_diet(idx):
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'diet' in p and 0 <= idx < len(p['diet']):
        p['diet'].pop(idx)
        save_patients(patients)
    return redirect('/dashboard')

# ── Doctor: Add Test ───────────────────────────────────────
@app.route('/add-test', methods=['POST'])
def add_test():
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'tests' not in p: p['tests'] = []
    p['tests'].append({
        "name": request.form.get('test_name', '').strip(),
        "date": request.form.get('test_date', '').strip(),
        "note": request.form.get('test_note', '').strip()
    })
    save_patients(patients)
    return redirect('/dashboard')

@app.route('/delete-test/<int:idx>', methods=['POST'])
def delete_test(idx):
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'tests' in p and 0 <= idx < len(p['tests']):
        p['tests'].pop(idx)
        save_patients(patients)
    return redirect('/dashboard')

# ── Doctor: Add Appointment ────────────────────────────────
@app.route('/add-appointment', methods=['POST'])
def add_appointment():
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'appointments' not in p: p['appointments'] = []
    date = request.form.get('appt_date', '').strip()
    time = request.form.get('appt_time', '').strip()
    note = request.form.get('appt_note', '').strip()
    p['appointments'].append({"date": date, "time": time, "note": note})
    save_patients(patients)
    return redirect('/dashboard')

@app.route('/delete-appointment/<int:idx>', methods=['POST'])
def delete_appointment(idx):
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'appointments' in p and 0 <= idx < len(p['appointments']):
        p['appointments'].pop(idx)
        save_patients(patients)
    return redirect('/dashboard')

# ── Groq AI Chatbot ────────────────────────────────────────
GROQ_API_KEY = ""
_last_chat_time = None

@app.route('/chat', methods=['POST'])
def chat():
    global _last_chat_time
    if not session.get('patient_logged_in'):
        return jsonify({'reply': 'Please login first.'})
    now = datetime.now()
    if _last_chat_time and (now - _last_chat_time).total_seconds() < 5:
        wait = int(5 - (now - _last_chat_time).total_seconds())
        return jsonify({'reply': f'⏳ Please wait {wait} more seconds.'})
    _last_chat_time = now
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        user_msg = request.json.get('message', '').strip()
        p = list(patients.values())[0]
        system = (
            f"You are a helpful medical assistant for a Smart Remote Patient Monitoring System. "
            f"Patient: {p['name']}, Age: {p['age']}. "
            f"Current vitals — Temp: {p['current_temp']}°C, BPM: {p['current_bpm']}, SpO2: {p.get('current_spo2',98)}%. "
            f"Only answer health, medicine, diet and wellness questions. "
            f"Keep answers short, clear and friendly. "
            f"If asked non-medical questions, politely say you only handle health topics."
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg}
            ],
            max_tokens=300
        )
        reply = response.choices[0].message.content
        if 'chat_history' not in p: p['chat_history'] = []
        p['chat_history'].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "question": user_msg,
            "answer": reply
        })
        p['chat_history'] = p['chat_history'][-50:]
        save_patients(patients)
        return jsonify({'reply': reply})
    except Exception as e:
        print(f"❌ Chat error: {e}")
        return jsonify({'reply': 'Sorry, something went wrong. Please try again.'})

# ── Patient Portal ─────────────────────────────────────────

@app.route('/patient-login', methods=['GET', 'POST'])
def patient_login():
    error = None
    if request.method == 'POST':
        patient_id = request.form.get('patient_id', '').strip()
        password   = request.form.get('password', '')
        if patient_id == 'P001' and password == 'Patient@1':
            session['patient_logged_in'] = True
            return redirect('/patient-dashboard')
        else:
            error = 'Invalid Patient ID or password.'
    return render_template('patient_login.html', error=error)

@app.route('/patient-dashboard')
def patient_dashboard():
    if not session.get('patient_logged_in'):
        return redirect('/patient-login')
    patients = load_patients()  # always fresh
    p = list(patients.values())[0]
    last_record = p['records'][-1] if p['records'] else None
    conditions, prevention = predict_disease(
        p['current_temp'], p['current_bpm'],
        p.get('current_spo2', 98), p.get('current_rr', 16)
    )
    labels, h_temps, h_bpms = get_hourly_data(p['records'])
    return render_template('patient_dashboard.html', patient=p,
                           last_record=last_record, prescriptions=p.get('prescriptions',[]),
                           conditions=conditions, prevention=prevention,
                           h_labels=labels, h_temps=h_temps, h_bpms=h_bpms)

@app.route('/patient-logout')
def patient_logout():
    session.pop('patient_logged_in', None)
    return redirect('/patient-login')

# ── Download Prescription PDF ──────────────────────────────
@app.route('/download-prescription')
def download_prescription():
    if not session.get('patient_logged_in') and 'patient_name' not in session:
        return redirect('/')
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    from flask import make_response

    p = list(patients.values())[0]

    # Strip emojis — PDF font doesn't support them
    import re
    def clean(text):
        return re.sub(r'[^\x00-\xFF]', '', str(text)).strip()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    def nl(pdf): pdf.ln(0)

    # Header bar
    pdf.set_fill_color(13, 33, 55)
    pdf.rect(0, 0, 210, 36, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_xy(15, 6)
    pdf.cell(180, 9, clean('Smart Remote Patient Monitoring System'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_x(15)
    pdf.cell(180, 7, clean('Apollo Hospital  |  Dr. A. Sharma  |  General Physician'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(15)
    pdf.cell(180, 7, clean('Tel: +91-9705875880  |  doctor@apollohealth.com'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Patient info
    pdf.set_fill_color(230, 240, 255)
    pdf.rect(15, 42, 180, 28, 'F')
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_xy(17, 44)
    pdf.cell(55, 7, f"Patient: {p['name']}")
    pdf.cell(55, 7, f"Age: {p['age']} yrs")
    pdf.cell(55, 7, "Gender: Male", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(17)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(55, 7, "Patient ID: P001")
    pdf.cell(55, 7, f"Date: {datetime.now().strftime('%d-%m-%Y')}")
    pdf.cell(55, 7, "Ward: ICU - Room 4B", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(17)
    pdf.set_font('Helvetica', 'B', 10)
    is_crit = p['current_temp'] > 32.4 or p['current_bpm'] > 90 or p['current_bpm'] < 70
    pdf.set_text_color(180, 0, 0) if is_crit else pdf.set_text_color(0, 130, 0)
    pdf.cell(180, 7, f"Status: {'CRITICAL' if is_crit else 'NORMAL'}  |  Temp: {p['current_temp']}C  |  BPM: {p['current_bpm']}  |  SpO2: {p.get('current_spo2',98)}%", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def sec(title, y):
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(13, 33, 55)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_xy(15, y)
        pdf.rect(15, y, 180, 8, 'F')
        pdf.set_xy(17, y+1)
        pdf.cell(176, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        return y + 12

    # Vitals
    y = sec('CURRENT VITALS', 76)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_xy(17, y)
    pdf.cell(45, 7, f"Temp: {p['current_temp']}C")
    pdf.cell(45, 7, f"BPM: {p['current_bpm']}")
    pdf.cell(45, 7, f"SpO2: {p.get('current_spo2',98)}%")
    pdf.cell(45, 7, f"RR: {p.get('current_rr',16)}/min", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(17)
    pdf.cell(90, 7, f"Sugar Fasting: {p.get('current_sugar_fasting','-')} mg/dL")
    pdf.cell(90, 7, f"Sugar PP: {p.get('current_sugar_pp','-')} mg/dL", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    y += 16

    # Prescription
    y = sec('PRESCRIPTION (Rx)', y + 4)
    for i, med in enumerate(p.get('prescriptions', []), 1):
        pdf.set_xy(17, y)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(8, 7, f"{i}.")
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(65, 7, clean(med.get('name', '')))
        pdf.cell(40, 7, clean(med.get('dose', '')))
        pdf.cell(0, 7, clean(med.get('timing', '')), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y += 7
        if y > 255: break

    # Diet
    y = sec('DIET INSTRUCTIONS', y + 4)
    for d in p.get('diet', []):
        pdf.set_xy(17, y)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(5, 7, '-')
        pdf.cell(75, 7, clean(d.get('item', '')))
        pdf.cell(0, 7, clean(d.get('note', '')), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y += 7
        if y > 255: break

    # Tests
    if y < 248:
        y = sec('PRESCRIBED TESTS', y + 4)
        for t in p.get('tests', []):
            pdf.set_xy(17, y)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(5, 7, '-')
            pdf.cell(65, 7, clean(t.get('name', '')))
            pdf.cell(35, 7, f"Date: {clean(t.get('date',''))}")
            pdf.cell(0, 7, f"{clean(t.get('note',''))} [{'Done' if t.get('done') else 'Pending'}]", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            y += 7
            if y > 255: break

    # Footer
    pdf.set_xy(15, 272)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(90, 6, f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    pdf.cell(90, 6, "Dr. A. Sharma  |  Signature: _______________", align='R')

    response = make_response(bytes(pdf.output()))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Prescription_{p["name"]}_{datetime.now().strftime("%d%m%Y")}.pdf'
    return response

# ── Patient: mark test as done ─────────────────────────────
@app.route('/patient-test-done/<int:idx>', methods=['POST'])
def patient_test_done(idx):
    if not session.get('patient_logged_in'): return redirect('/patient-login')
    p = list(patients.values())[0]
    if 'tests' in p and 0 <= idx < len(p['tests']):
        p['tests'][idx]['done'] = True
        p['tests'][idx]['done_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        p['tests'][idx]['result'] = request.form.get('result', '').strip()
    save_patients(patients)
    return redirect('/patient-dashboard')

# ── Vendor Portal ──────────────────────────────────────────
@app.route('/vendor-login', methods=['GET', 'POST'])
def vendor_login():
    error = None
    if request.method == 'POST':
        vendor_id = request.form.get('vendor_id', '').strip()
        password  = request.form.get('password', '')
        if vendor_id == 'Santosh' and password == 'Appollo':
            session['vendor_logged_in'] = True
            return redirect('/vendor-dashboard')
        else:
            error = 'Invalid Vendor ID or password.'
    return render_template('vendor_login.html', error=error)

@app.route('/vendor-dashboard')
def vendor_dashboard():
    if not session.get('vendor_logged_in'):
        return redirect('/vendor-login')
    p = list(patients.values())[0]
    # Build orders from prescriptions with status
    if 'prescriptions' not in p: p['prescriptions'] = []
    for med in p['prescriptions']:
        if 'status' not in med or med['status'] == 'Active':
            med['order_status'] = med.get('order_status', 'Pending')
    orders = [{'name': m['name'], 'dose': m['dose'], 'timing': m['timing'],
                'status': m.get('order_status', 'Pending')} for m in p['prescriptions']]
    pending    = sum(1 for o in orders if o['status'] == 'Pending')
    dispatched = sum(1 for o in orders if o['status'] == 'Dispatched')
    delivered  = sum(1 for o in orders if o['status'] == 'Delivered')
    return render_template('vendor_dashboard.html', patient=p, orders=orders,
                           pending=pending, dispatched=dispatched, delivered=delivered)

@app.route('/vendor-update/<int:idx>/<status>', methods=['POST'])
def vendor_update(idx, status):
    if not session.get('vendor_logged_in'): return redirect('/vendor-login')
    p = list(patients.values())[0]
    if 'prescriptions' in p and 0 <= idx < len(p['prescriptions']):
        p['prescriptions'][idx]['order_status'] = status
        save_patients(patients)
    return redirect('/vendor-dashboard')

@app.route('/vendor-logout')
def vendor_logout():
    session.pop('vendor_logged_in', None)
    return redirect('/vendor-login')

@app.route('/refer-to-specialist', methods=['POST'])
def refer_to_specialist():
    if 'patient_name' not in session: return redirect('/')
    p = list(patients.values())[0]
    if 'referral' not in p: p['referral'] = {}
    p['referral']['reason']      = request.form.get('reason', '').strip()
    p['referral']['specialist']  = request.form.get('specialist', '').strip()
    p['referral']['referred_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p['referral']['status']      = 'Pending'
    p['referral']['specialist_notes']     = ''
    p['referral']['specialist_diagnosis'] = ''
    p['referral']['specialist_rx']        = ''
    p['referral']['responded_by']         = ''
    p['referral']['responded_at']         = ''
    save_patients(patients)
    return redirect('/dashboard')

# ── Specialist Doctor Portal ───────────────────────────────
SPECIALISTS = [
    {"id": "CARDIO01", "password": "Cardio@1", "name": "Dr. Priya Mehta", "specialty": "Cardiologist", "hospital": "Apollo Hospital, Mumbai"},
    {"id": "NEURO01",  "password": "Neuro@1",  "name": "Dr. Rahul Verma", "specialty": "Neurologist",  "hospital": "Fortis Hospital, Delhi"},
    {"id": "GENERAL01","password": "General@1","name": "Dr. Sneha Patil",  "specialty": "General Physician","hospital": "Lilavati Hospital, Mumbai"},
]

@app.route('/specialist-login', methods=['GET', 'POST'])
def specialist_login():
    error = None
    if request.method == 'POST':
        sid  = request.form.get('specialist_id', '').strip()
        pwd  = request.form.get('password', '')
        spec = next((s for s in SPECIALISTS if s['id'] == sid and s['password'] == pwd), None)
        if spec:
            session['specialist_id']   = spec['id']
            session['specialist_name'] = spec['name']
            return redirect('/specialist-dashboard')
        else:
            error = 'Invalid Specialist ID or password.'
    return render_template('specialist_login.html', error=error)

@app.route('/specialist-dashboard')
def specialist_dashboard():
    if not session.get('specialist_id'): return redirect('/specialist-login')
    p    = list(patients.values())[0]
    spec = next((s for s in SPECIALISTS if s['id'] == session['specialist_id']), SPECIALISTS[0])
    last_record = p['records'][-1] if p['records'] else None
    conditions, prevention = predict_disease(
        p['current_temp'], p['current_bpm'],
        p.get('current_spo2', 98), p.get('current_rr', 16)
    )
    referral = p.get('referral', {})
    return render_template('specialist_dashboard.html', patient=p, spec=spec,
                           last_record=last_record, conditions=conditions,
                           prevention=prevention, referral=referral)

@app.route('/specialist-respond', methods=['POST'])
def specialist_respond():
    if not session.get('specialist_id'): return redirect('/specialist-login')
    p = list(patients.values())[0]
    spec = next((s for s in SPECIALISTS if s['id'] == session['specialist_id']), SPECIALISTS[0])
    if 'referral' not in p: p['referral'] = {}
    p['referral']['specialist_notes']    = request.form.get('notes', '').strip()
    p['referral']['specialist_diagnosis']= request.form.get('diagnosis', '').strip()
    p['referral']['specialist_rx']       = request.form.get('rx', '').strip()
    p['referral']['responded_by']        = spec['name']
    p['referral']['responded_at']        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p['referral']['status']              = 'Responded'
    save_patients(patients)
    return redirect('/specialist-dashboard')

@app.route('/specialist-logout')
def specialist_logout():
    session.pop('specialist_id', None)
    session.pop('specialist_name', None)
    return redirect('/specialist-login')

if __name__ == '__main__':
    print("🚀 Health Monitor LIVE!")
    print("✅ Doctor  : http://10.196.205.60:5000")
    print("✅ Patient : http://10.196.205.60:5000/patient-login")
    app.run(host='0.0.0.0', port=5000, debug=True)
