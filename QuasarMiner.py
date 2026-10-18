#!/usr/bin/env python3
# ============================================================
#  QUASAR MINING - One-Click GUI Miner  (v2)
#  Double-click START-MINING.bat. No typing. No black window.
#  No PowerShell, no .vbs - pure Python, so Windows cannot
#  block it with execution-policy or script warnings.
#
#  The big button does everything automatically:
#    components -> wallet -> seed -> miner starts hidden ->
#    live status. Plus:
#    * a tiny local web server (127.0.0.1:9334) so the Quasar
#      website dashboard can show START/STOP + live Block and
#      Balance - the miner never needs its folder opened again.
#    * "Start with Windows" checkbox - mining resumes on its
#      own after every reboot.
# ============================================================

import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------- paths & constants ----------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "quasar-seed")
PID_FILE = os.path.join(DATA_DIR, "miner.pid")
SEED_FILE = os.path.join(SCRIPT_DIR, "seed.txt")
CLI = os.path.join(SCRIPT_DIR, "quasar_cli.py")
LOCAL_PORT = 9334  # local control server for the website dashboard
NODE_PORT = 9333   # P2P port the node listens on

# Make every quasar_cli call (new-address, balance, info) use the same
# data dir as the node itself - exactly like the v1 launcher did.
os.environ["QUASAR_DATA_DIR"] = DATA_DIR

# pythonw = no console window at all. If we were started with
# python.exe, prefer the pythonw.exe sitting next to it.
if os.path.basename(sys.executable).lower().startswith("pythonw"):
    PYW = sys.executable
else:
    _cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    PYW = _cand if os.path.exists(_cand) else sys.executable


def log(msg):
    """Thread-safe log writer - the GUI wires this up on start."""
    line = "[%s] %s\n" % (time.strftime("%H:%M:%S"), msg)
    try:
        _ui_log(line)
    except Exception:
        pass


_ui_log = lambda line: sys.stderr.write(line)  # replaced by GUI


# ---------------- miner helpers ----------------

def read_seed():
    """seed.txt ships pre-filled inside the zip - no manual step."""
    try:
        with open(SEED_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "REPLACE_THIS" in line:
                    continue
                return line
    except OSError:
        pass
    return ""


def run_cli(*args, timeout=25):
    """Run quasar_cli.py and return stdout ('' on failure)."""
    try:
        out = subprocess.run(
            [sys.executable, CLI, *args],
            cwd=SCRIPT_DIR,
            capture_output=True, text=True, timeout=timeout,
        )
        return out.stdout or ""
    except Exception:
        return ""


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def read_pid():
    try:
        with open(PID_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None


def write_pid(pid):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PID_FILE, "w") as f:
            f.write(str(pid))
    except Exception:
        pass


def _node_port_pids():
    """PIDs listening on the node P2P port (Windows netstat -ano).

    Reliable on Windows 11 where wmic no longer exists. If anything
    listens on NODE_PORT locally, a quasar node is up - typically a
    previous miner that was never stopped.
    """
    pids = set()
    if os.name != "nt":
        return pids
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                             capture_output=True, text=True,
                             timeout=10).stdout
    except Exception:
        return pids
    for line in out.splitlines():
        # e.g. "  TCP    0.0.0.0:9333    0.0.0.0:0    LISTENING    1234"
        m = re.search(r"TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)", line)
        if m and int(m.group(1)) == NODE_PORT:
            pid = int(m.group(2))
            if pid != os.getpid():
                pids.add(pid)
    return pids


def miner_running():
    pid = read_pid()
    if pid and pid_alive(pid):
        return True
    # Fallback: a node from a previous session (e.g. the v1 miner)
    # holds the P2P port even though we have no PID file for it.
    if os.name == "nt" and _node_port_pids():
        return True
    return False


def kill_stale_node():
    """Stop any node holding the P2P port (old miner left running)."""
    killed = False
    for pid in _node_port_pids():
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=10)
            killed = True
        except Exception:
            pass
    return killed


def get_height():
    info = run_cli("info")
    m = re.search(r"Chain height:\s+(\d+)", info)
    return m.group(1) if m else "?"


def get_balance():
    bal = run_cli("balance", "miner")
    m = re.search(r":\s*([0-9,\.]+)\s*QSR", bal)
    return m.group(1) if m else "?"


def start_miner():
    """Full one-click start sequence. Returns True when mining."""
    os.makedirs(DATA_DIR, exist_ok=True)

    log("Preparing components...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "--disable-pip-version-check", "ecdsa"],
            capture_output=True, timeout=180,
        )
    except Exception as e:
        log("Component step warning: %s" % e)
    log("Components ready - OK.")

    wallet_path = os.path.join(DATA_DIR, "wallets", "miner.json")
    if not os.path.exists(wallet_path):
        log("Creating your wallet (one time only)...")
        run_cli("new-address", "miner")
        log("Wallet created - OK.")
    else:
        log("Wallet found - OK.")

    pid = read_pid()
    if pid and pid_alive(pid):
        log("Miner already running - attaching.")
        return True
    # A node from a previous session (e.g. the v1 miner left running)
    # still holds the P2P port - stop it so the new node can start.
    if os.name == "nt" and _node_port_pids():
        log("Old miner found still running - stopping it...")
        kill_stale_node()
        time.sleep(3)
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except Exception:
            pass

    seed = read_seed()
    args = ["start-node", "--datadir", DATA_DIR, "--mine-auto", "miner"]
    if seed:
        args += ["--seed", seed]
        log("Joining network seed...")
    log("Starting miner in background (no window)...")

    kwargs = dict(cwd=SCRIPT_DIR, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    if os.name == "nt":
        DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        kwargs["creationflags"] = DETACHED | NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen([PYW, CLI, *args], **kwargs)
    write_pid(proc.pid)
    time.sleep(4)

    if miner_running():
        log("MINING STARTED - new coins every ~30 sec go to your wallet.")
        return True
    log("Miner did not stay up - press START MINING again.")
    return False


def stop_miner():
    log("Stopping miner...")
    pid = read_pid()
    if pid:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=10)
            else:
                os.kill(pid, 15)
        except Exception:
            pass
    # Fallback sweep: kill anything still holding the P2P port.
    if os.name == "nt":
        kill_stale_node()
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass
    log("Stopped. Coins are saved - nothing is lost.")


# ---------------- auto-start with Windows ----------------

def startup_bat_path():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup",
                        "QuasarMiner-AutoStart.bat")


def autostart_enabled():
    return os.path.exists(startup_bat_path())


def set_autostart(on):
    p = startup_bat_path()
    try:
        if on:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write('@echo off\r\nstart "" /min pythonw "%s"\r\n'
                        % os.path.join(SCRIPT_DIR, "QuasarMiner.py"))
            log("Auto-start ON - mining will resume after every reboot.")
        else:
            if os.path.exists(p):
                os.remove(p)
            log("Auto-start OFF.")
        return True
    except Exception as e:
        log("Auto-start change failed: %s" % e)
        return False


# ---------------- local control server (website dashboard) ----------------
# The public website can reach http://127.0.0.1:9334 because browsers
# treat localhost as a secure context. Endpoints:
#   GET  /status -> {"mining":true,"height":"9908","balance":"350,000"}
#   POST /start  -> starts mining
#   POST /stop   -> stops mining

class _Handler(BaseHTTPRequestHandler):
    server_version = "QuasarMiner/2"

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        if self.path == "/status":
            mining = miner_running()
            self._send({
                "mining": mining,
                "height": get_height() if mining else "?",
                "balance": get_balance() if mining else "?",
            })
        else:
            self._send({"ok": False, "error": "unknown endpoint"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)
        if self.path == "/start":
            ok = start_miner()
            try:
                _ui_after_start(ok)
            except Exception:
                pass
            self._send({"ok": ok, "mining": miner_running()})
        elif self.path == "/stop":
            stop_miner()
            try:
                _ui_after_stop()
            except Exception:
                pass
            self._send({"ok": True, "mining": False})
        else:
            self._send({"ok": False, "error": "unknown endpoint"}, 404)

    def log_message(self, *args):
        pass


_ui_after_start = lambda ok: None  # replaced by GUI
_ui_after_stop = lambda: None      # replaced by GUI


def serve_forever():
    try:
        srv = HTTPServer(("127.0.0.1", LOCAL_PORT), _Handler)
        srv.serve_forever()
    except OSError as e:
        log("Local dashboard link busy (port %d): %s" % (LOCAL_PORT, e))


# ---------------- GUI ----------------

class MinerGUI:
    def __init__(self, root):
        self.root = root
        self.mining = False
        root.title("Quasar Mining")
        root.geometry("520x500")
        root.resizable(False, False)
        root.configure(bg="#fff8f0")

        title_f = tkfont.Font(family="Segoe UI", size=20, weight="bold")
        tk.Label(root, text="QUASAR MINING", font=title_f,
                 fg="#c85a0a", bg="#fff8f0").place(x=20, y=15)
        tk.Label(root, text="One click. No typing. No black window.",
                 font=("Segoe UI", 10), fg="#5a463c",
                 bg="#fff8f0").place(x=22, y=52)

        self.status = tk.Label(root, text="Ready. Press START MINING.",
                               font=("Segoe UI", 11, "bold"),
                               fg="#333333", bg="#fff8f0",
                               anchor="w", justify="left")
        self.status.place(x=20, y=82, width=460, height=30)

        self.start_btn = tk.Button(root, text="START MINING",
                                  font=("Segoe UI", 14, "bold"),
                                  bg="gold", activebackground="#ffd700",
                                  relief="flat", cursor="hand2",
                                  command=self.on_start)
        self.start_btn.place(x=20, y=120, width=220, height=60)

        self.stop_btn = tk.Button(root, text="STOP",
                                 font=("Segoe UI", 12, "bold"),
                                 relief="flat", cursor="hand2",
                                 state="disabled", command=self.on_stop)
        self.stop_btn.place(x=260, y=120, width=220, height=60)

        self.auto_var = tk.BooleanVar(value=autostart_enabled())
        self.auto_chk = tk.Checkbutton(
            root, text="Start mining automatically with Windows",
            variable=self.auto_var, font=("Segoe UI", 10),
            bg="#fff8f0", fg="#5a463c", cursor="hand2",
            command=self.on_autostart)
        self.auto_chk.place(x=20, y=190)

        self.logbox = tk.Text(root, font=("Consolas", 9), wrap="word",
                             state="disabled", bg="#ffffff")
        self.logbox.place(x=20, y=220, width=460, height=240)
        sb = tk.Scrollbar(root, command=self.logbox.yview)
        sb.place(x=480, y=220, width=16, height=240)
        self.logbox.configure(yscrollcommand=sb.set)

        global _ui_log, _ui_after_start, _ui_after_stop
        _ui_log = self._log
        _ui_after_start = self._after_start
        _ui_after_stop = self._after_stop

        self._log_line("Welcome to Quasar Mining. Press START MINING.")
        # If the miner is already running (e.g. auto-started), attach.
        if miner_running():
            self.mining = True
            self._after_start(True)
            self._log_line("Attached to running miner.")
        self.root.after(10000, self._poll)

    def _log_line(self, line):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", line)
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _log(self, line):
        self.root.after(0, self._log_line, line)

    def _set_status(self, text, color):
        self.status.configure(text=text, fg=color)

    def on_start(self):
        self.start_btn.configure(state="disabled")
        self._log_line("[%s] Starting...\n" % time.strftime("%H:%M:%S"))
        threading.Thread(target=self._do_start, daemon=True).start()

    def _do_start(self):
        ok = start_miner()
        self.root.after(0, self._after_start, ok)

    def _after_start(self, ok):
        if ok:
            self.mining = True
            self.stop_btn.configure(state="normal")
            self.start_btn.configure(state="disabled")
            self._poll()
        else:
            self.start_btn.configure(state="normal")

    def on_stop(self):
        threading.Thread(target=self._do_stop, daemon=True).start()

    def _do_stop(self):
        stop_miner()
        self.root.after(0, self._after_stop)

    def _after_stop(self):
        self.mining = False
        self._set_status("Miner stopped. Coins are saved - nothing is lost.",
                        "#8b0000")
        self.stop_btn.configure(state="disabled")
        self.start_btn.configure(state="normal")

    def on_autostart(self):
        set_autostart(self.auto_var.get())

    def _poll(self):
        if not self.mining:
            return
        if not miner_running():
            self._after_stop()
            self._log_line("Miner process ended.\n")
            return
        h, b = get_height(), get_balance()
        self._set_status("Mining...   Block %s    |    Balance %s QSR"
                         % (h, b), "#006400")
        self.root.after(10000, self._poll)


def main():
    threading.Thread(target=serve_forever, daemon=True).start()
    root = tk.Tk()
    MinerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
