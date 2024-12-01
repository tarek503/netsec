from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import threading
import os
import re
import time
import logging
import requests
from threading import Lock

# Flask app and SocketIO setup
app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')

# Global variables
network_activity = {"connections": 0, "unique_ips": 0}
monitoring = False
activity_lock = Lock()

# Logger setup
logger = logging.getLogger('web_ddos_detector')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('ddos_logs.log', mode='a')
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S%p')
handler.setFormatter(formatter)
handler.setStream(open('ddos_logs.log', 'a', buffering=1))
logger.addHandler(handler)

def monitor_network():
    global monitoring
    while monitoring:
        try:
            with activity_lock:
                ip_list = []
                with open("ddos_logs.log", "r") as f:
                    logs = f.readlines()
                    for line in logs:
                        match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                        if match:
                            ip_list.append(match.group(1))

                connections = len(ip_list)
                unique_ips = len(set(ip_list))
                network_activity["connections"] = connections
                network_activity["unique_ips"] = unique_ips

                # Debugging logs
                logger.info(f"Monitoring: Connections={connections}, Unique IPs={unique_ips}")

                # Emit updates to frontend
                socketio.emit("update", {"connections": connections, "unique_ips": unique_ips})

                # Check for potential DDoS
                if connections > 50:  # Lower threshold for testing
                    attacker = max(set(ip_list), key=ip_list.count) if ip_list else "Unknown"
                    alert = f"Potential DDoS detected. Connections: {connections}, Attacker: {attacker}"
                    logger.warning(alert)
                    socketio.emit("alert", {"message": alert})

            time.sleep(5)  # Avoid excessive CPU usage
        except Exception as e:
            logger.error(f"Error in monitoring: {e}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start_monitoring", methods=["POST"])
def start_monitoring():
    global monitoring
    if not monitoring:
        monitoring = True
        threading.Thread(target=monitor_network, daemon=True).start()
    return jsonify({"status": "Monitoring started"})

@app.route("/stop_monitoring", methods=["POST"])
def stop_monitoring():
    global monitoring
    monitoring = False
    return jsonify({"status": "Monitoring stopped"})

def simulate_normal_traffic():
    url = "http://127.0.0.1:5000/"
    for _ in range(100):
        try:
            requests.get(url)
        except Exception as e:
            logger.error(f"Error simulating normal traffic: {e}")

def simulate_http_flood():
    target_host = "127.0.0.1"
    target_port = 5000

    def flood():
        while monitoring:  # Stop when monitoring stops
            try:
                requests.get(f"http://{target_host}:{target_port}/")
            except Exception as e:
                logger.error(f"Error simulating HTTP flood: {e}")

    for _ in range(10):  # Launch multiple threads
        threading.Thread(target=flood, daemon=True).start()

@app.route("/simulate/normal", methods=["POST"])
def simulate_normal():
    threading.Thread(target=simulate_normal_traffic, daemon=True).start()
    return jsonify({"status": "Simulating normal traffic"})

@app.route("/simulate/attack", methods=["POST"])
def simulate_attack():
    threading.Thread(target=simulate_http_flood, daemon=True).start()
    return jsonify({"status": "Simulating HTTP flood attack"})

@socketio.on("connect")
def handle_connect():
    logger.info("Frontend connected.")

@socketio.on("disconnect")
def handle_disconnect():
    logger.info("Frontend disconnected.")

if __name__ == "__main__":
    socketio.run(app, debug=True)
