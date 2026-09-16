import time
import socket
import psutil
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
START_TIME = time.time()

# Simulated "unhealthy after N sec" toggle for demo (optional, off by default)
FORCE_FAIL_AFTER = None  # e.g. set to 120 to test auto-restart

HTML = """
<!doctype html>
<title>Infra Monitor</title>
<style>
body{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:40px}
h1{color:#58a6ff} .card{background:#161b22;padding:16px;border-radius:8px;margin:10px 0}
.ok{color:#3fb950} .bad{color:#f85149}
</style>
<h1>🖥️ Infra Monitor — {{host}}</h1>
<div class="card">Status: <span class="ok">HEALTHY</span></div>
<div class="card">Uptime: {{uptime}}s</div>
<div class="card">CPU: {{cpu}}%</div>
<div class="card">Memory: {{mem}}%</div>
<div class="card">Disk: {{disk}}%</div>
<p>Endpoints: <a href="/health">/health</a> | <a href="/metrics">/metrics</a></p>
"""

def uptime():
    return round(time.time() - START_TIME, 1)

def is_healthy():
    if FORCE_FAIL_AFTER and uptime() > FORCE_FAIL_AFTER:
        return False
    return True

@app.route("/")
def dashboard():
    return render_template_string(
        HTML,
        host=socket.gethostname(),
        uptime=uptime(),
        cpu=psutil.cpu_percent(interval=0.2),
        mem=psutil.virtual_memory().percent,
        disk=psutil.disk_usage("/").percent,
    )

@app.route("/health")
def health():
    # Liveness probe hits this — K8s restarts container if this fails
    if not is_healthy():
        return jsonify(status="unhealthy"), 500
    return jsonify(status="healthy", uptime=uptime(), host=socket.gethostname()), 200

@app.route("/ready")
def ready():
    # Readiness probe — K8s pulls pod out of Service rotation if this fails
    ready_ok = uptime() > 3  # simulate warm-up delay
    if not ready_ok:
        return jsonify(status="not_ready"), 503
    return jsonify(status="ready"), 200

@app.route("/metrics")
def metrics():
    return jsonify(
        host=socket.gethostname(),
        uptime_seconds=uptime(),
        cpu_percent=psutil.cpu_percent(interval=0.2),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage("/").percent,
    )

@app.route("/crash")
def crash():
    # Manually trigger a crash to prove K8s self-heals (demo endpoint)
    import os
    os._exit(1)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
