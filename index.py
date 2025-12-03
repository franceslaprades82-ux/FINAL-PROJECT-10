from flask import Flask, Response, request, jsonify, render_template_string, redirect, session
import os
import requests
from noise_monitor import create_monitor

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = "supersecretkey123"

# ===== ESP32-CAM Base IP =====
ESP_BASE = "http://192.168.1.10"  # Updated ESP32 IP

# ===== Login system =====
LOGIN_PAGE = open("static/login.html").read()
USERNAME = "admin"
PASSWORD = "1234"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template_string(LOGIN_PAGE)
    username = request.form.get("username")
    password = request.form.get("password")
    if username == USERNAME and password == PASSWORD:
        session["logged_in"] = True
        return redirect("/")
    return render_template_string(LOGIN_PAGE, error="Invalid username or password")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

def require_login():
    return "logged_in" in session

# ===== Initialize NoiseMonitor =====
monitor = create_monitor(esp_base=ESP_BASE, enable_buzzer=False)
monitor.start()

# ===== Dashboard pages =====
@app.route('/')
def index_page():
    if not require_login():
        return redirect("/login")
    return app.send_static_file('index.html')

@app.route('/incidents')
def incidents_page():
    if not require_login():
        return redirect("/login")
    return app.send_static_file('incidents.html')

# ===== API: Noise logs =====
@app.route('/api/incidents')
def api_incidents():
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 403
    logs = monitor.get_logs(limit=100)
    logs_out = [{'timestamp': ts, 'noise': noise, 'alerted': bool(alerted)} for ts, noise, alerted in logs]
    return jsonify(logs_out)

# ===== API: Threshold =====
@app.route('/api/threshold', methods=['GET', 'POST'])
def api_threshold():
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 403

    if request.method == 'GET':
        return jsonify({'threshold': monitor.get_threshold()})

    data = request.json
    if not data or 'threshold' not in data:
        return jsonify({'ok': False, 'error': 'Missing threshold'}), 400

    try:
        value = float(data['threshold'])
        monitor.set_threshold(value)
        return jsonify({'ok': True, 'threshold': value})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ===== Camera Stream (proxy MJPEG from ESP32) =====
@app.route("/video_feed")
def video_feed():
    if not require_login():
        return redirect("/login")

    def generate():
        import requests
        with requests.get(f"{ESP_BASE}/stream", stream=True) as r:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ===== API: Camera Status =====
@app.route('/api/camera_status')
def api_camera_status():
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 403
    try:
        r = requests.get(f"{ESP_BASE}/capture", timeout=3)
        return jsonify({'connected': r.status_code == 200})
    except:
        return jsonify({'connected': False})

# ===== Servo control =====
@app.route('/servo_x', methods=['POST'])
def servo_x():
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 403
    angle = int(request.json.get('angle', 90))
    angle = max(0, min(180, angle))
    try:
        requests.get(f"{ESP_BASE}/servo_x?angle={angle}", timeout=1)
        return jsonify({'ok': True, 'angle': angle})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/servo_y', methods=['POST'])
def servo_y():
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 403
    angle = int(request.json.get('angle', 90))
    angle = max(0, min(180, angle))
    try:
        requests.get(f"{ESP_BASE}/servo_y?angle={angle}", timeout=1)
        return jsonify({'ok': True, 'angle': angle})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ===== Buzzer control =====
@app.route('/buzzer', methods=['POST'])
def buzzer_control():
    if not require_login():
        return jsonify({'error': 'Not logged in'}), 403
    action = int(request.json.get('on', 0))
    try:
        if action:
            requests.get(f"{ESP_BASE}/buzzer_on", timeout=1)
        else:
            requests.get(f"{ESP_BASE}/buzzer_off", timeout=1)
        return jsonify({'ok': True, 'action': action})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ===== Run App =====
if __name__ == '__main__':
    os.makedirs('recordings', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
