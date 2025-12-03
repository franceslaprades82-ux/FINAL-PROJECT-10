import threading
import time
import requests
import random
import sqlite3
from datetime import datetime

DB = "noise.db"
ESP_DEFAULT_BASE = "http://192.168.1.10"  # Change to your ESP32-CAM IP
class NoiseMonitor:
    def __init__(self, esp_base=ESP_DEFAULT_BASE, poll_interval=1.0, enable_buzzer=False):
        self.esp_base = esp_base.rstrip('/')
        self.poll_interval = poll_interval
        self.enable_buzzer = enable_buzzer
        self.current_noise = 0.0
        self._stop = threading.Event()
        self._thread = None
        self._last_alert_time = 0

        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                noise REAL,
                alerted INTEGER
            )
        ''')
        # default threshold if not present
        c.execute("SELECT value FROM settings WHERE key = 'threshold'")
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO settings (key, value) VALUES (?,?)", ('threshold', '60'))
        conn.commit()
        conn.close()

    def get_threshold(self):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'threshold'")
        row = c.fetchone()
        conn.close()
        if row:
            try:
                return float(row[0])
            except:
                return 60.0
        return 60.0

    def set_threshold(self, value):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ('threshold', str(value)))
        conn.commit()
        conn.close()

    def get_logs(self, limit=100):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT ts, noise, alerted FROM logs ORDER BY id DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return rows

    def _save_log(self, noise, alerted):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO logs (ts, noise, alerted) VALUES (?, ?, ?)",
                  (datetime.utcnow().isoformat(), float(noise), int(bool(alerted))))
        conn.commit()
        conn.close()

    def _read_from_esp(self):
        """
        Tries to call ESP endpoint /noise which should return JSON {"noise": 55.2}
        Fallback: try /noise_level or /sound, otherwise simulate.
        """
        candidates = [
            f"{self.esp_base}/noise",
            f"{self.esp_base}/noise_level",
            f"{self.esp_base}/sound",
            f"{self.esp_base}/get_noise"
        ]
        for url in candidates:
            try:
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, dict) and 'noise' in j:
                        return float(j['noise'])
                    # maybe plain number
                    try:
                        return float(j)
                    except:
                        pass
            except Exception:
                pass
        # last resort: try an endpoint that returns plain text
        try:
            r = requests.get(f"{self.esp_base}/noise.txt", timeout=2)
            if r.status_code == 200:
                return float(r.text.strip())
        except Exception:
            pass
        # simulate if nothing available
        return None

    def _maybe_trigger_buzzer(self):
        # optional: short debounce to avoid spamming
        if not self.enable_buzzer:
            return
        now = time.time()
        if now - self._last_alert_time < 5:
            return
        try:
            # beep for 1 second (ESP endpoint must support this)
            requests.get(f"{self.esp_base}/buzzer?on=1", timeout=1)
            time.sleep(1)
            requests.get(f"{self.esp_base}/buzzer?on=0", timeout=1)
            self._last_alert_time = now
        except Exception:
            pass

    def _poll_loop(self):
        while not self._stop.is_set():
            val = None
            try:
                val = self._read_from_esp()
            except Exception:
                val = None

            if val is None:
                # simulated noise 30-80 dB
                val = round(random.uniform(30.0, 80.0), 1)

            self.current_noise = float(val)
            threshold = self.get_threshold()
            alerted = False
            if self.current_noise >= threshold:
                alerted = True
                self._save_log(self.current_noise, 1)
                # optionally cause buzzer on the ESP
                if self.enable_buzzer:
                    self._maybe_trigger_buzzer()
            else:
                # optionally still log non alerts periodically
                self._save_log(self.current_noise, 0)
            time.sleep(self.poll_interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def get_current(self):
        return round(float(self.current_noise or 0.0), 1)

# helper: create a default monitor instance if imported
_monitor_singleton = None

def create_monitor(esp_base=ESP_DEFAULT_BASE, poll_interval=1.0, enable_buzzer=False):
    global _monitor_singleton
    if _monitor_singleton is None:
        _monitor_singleton = NoiseMonitor(esp_base=esp_base, poll_interval=poll_interval, enable_buzzer=enable_buzzer)
    return _monitor_singleton
