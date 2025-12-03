from flask import Flask, Response, request, jsonify, render_template_string, redirect, session
import os
import requests
import time
from noise_monitor import create_monitor

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = "supersecretkey123"

ESP_BASE = "http://192.168.1.10"

LOGIN_PAGE = open("static/login.html").read()
USERNAME = "admin"
PASSWORD = "1234"

def require_login():
    return "logged_in" in session

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

# Initialize Noise Monitor
monitor = create_monitor(esp_base=ESP_BASE, enable_buzzer=False)
monitor.start()

@app.route("/")
def index_page():
    if not require_login():
        return redirect("/login")
    return app.send_static_file("index.html")

@app.route("/incidents")
def incidents_page():
    if not require_login():
        return redirect("/login")
    return app.send_static_file("incidents.html")

# ----------------- Camera feed -----------------
@app.route("/video_feed_snapshot")
def video_feed_snapshot():
    if not require_login():
        return redirect("/login")
    try:
        r = requests.get(f"{ESP_BASE}/capture", timeout=2)
        if r.status_code == 200:
            return Response(r.content, mimetype="image/jpeg")
    except Exception as e:
        print("Snapshot error:", e)
    return "", 500


# ----------------- Camera status -----------------
@app.route("/api/camera_status")
def api_camera_status():
    if not require_login():
        return jsonify({"error": "Not logged in"}), 403
    try:
        r = requests.get(f"{ESP_BASE}/capture", timeout=2)
        return jsonify({"connected": r.status_code == 200})
    except:
        return jsonify({"connected": False})

# ----------------- Noise logs -----------------
@app.route("/api/incidents")
def api_incidents():
    if not require_login():
        return jsonify({"error": "Not logged in"}), 403
    logs = monitor.get_logs(limit=100)
    return jsonify([{"timestamp": ts, "noise": noise, "alerted": bool(alerted)} for ts, noise, alerted in logs])

# ----------------- Threshold -----------------
@app.route("/api/threshold", methods=["GET","POST"])
def api_threshold():
    if not require_login():
        return jsonify({"error": "Not logged in"}), 403
    if request.method == "GET":
        return jsonify({"threshold": monitor.get_threshold()})
    data = request.json
    if not data or "threshold" not in data:
        return jsonify({"ok": False, "error": "Missing threshold"}), 400
    try:
        val = float(data["threshold"])
        monitor.set_threshold(val)
        return jsonify({"ok": True, "threshold": val})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ----------------- Servo -----------------
@app.route("/servo_x", methods=["POST"])
def servo_x():
    if not require_login():
        return jsonify({"error":"Not logged in"}),403
    angle = int(request.json.get("angle",90))
    angle = max(0,min(180,angle))
    try:
        requests.get(f"{ESP_BASE}/servo_x?angle={angle}",timeout=1)
        return jsonify({"ok": True, "angle": angle})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}),500

@app.route("/servo_y", methods=["POST"])
def servo_y():
    if not require_login():
        return jsonify({"error":"Not logged in"}),403
    angle = int(request.json.get("angle",90))
    angle = max(0,min(180,angle))
    try:
        requests.get(f"{ESP_BASE}/servo_y?angle={angle}",timeout=1)
        return jsonify({"ok": True, "angle": angle})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}),500

# ----------------- Buzzer -----------------
@app.route("/buzzer",methods=["POST"])
def buzzer_control():
    if not require_login():
        return jsonify({"error":"Not logged in"}),403
    action = int(request.json.get("on",0))
    try:
        if action:
            requests.get(f"{ESP_BASE}/buzzer_on",timeout=1)
        else:
            requests.get(f"{ESP_BASE}/buzzer_off",timeout=1)
        return jsonify({"ok": True, "action": action})
    except Exception as e:
        return jsonify({"ok": False,"error": str(e)}),500

# ----------------- Run -----------------
if __name__ == "__main__":
    os.makedirs("recordings",exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
