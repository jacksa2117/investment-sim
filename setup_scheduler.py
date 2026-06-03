"""
Windows Task Scheduler setup for Investment Simulation.

Three scheduled tasks:
  InvestmentSim_Morning    — All 6 agents,              Mon-Fri 09:00 ET
  InvestmentSim_Afternoon  — Speculator + Emotional,    Mon-Fri 15:45 ET
  InvestmentSim_Crypto     — Speculator crypto-only,    Daily every 4 hours 24/7

Usage:
  python setup_scheduler.py install    # create all 3 tasks (run as Administrator)
  python setup_scheduler.py remove     # delete all 3 tasks
  python setup_scheduler.py status     # show task info
  python setup_scheduler.py run-now <morning|afternoon|crypto>
"""

import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON   = sys.executable
RUNNER   = os.path.join(BASE_DIR, "runner.py")
LOG_DIR  = os.path.join(BASE_DIR, "data")
GH_BIN   = r"C:\Users\jack\gh-cli\bin\gh.exe"

TASKS = {
    "InvestmentSim_Morning": {
        "mode":    "morning",
        "desc":    "All 6 agents — daily at market open",
        "log":     os.path.join(LOG_DIR, "morning.log"),
        "schtask": [
            "/sc", "WEEKLY",
            "/d",  "MON,TUE,WED,THU,FRI",
            "/st", "09:00",
        ],
    },
    "InvestmentSim_Afternoon": {
        "mode":    "afternoon",
        "desc":    "Speculator + Emotional — pre-market close",
        "log":     os.path.join(LOG_DIR, "afternoon.log"),
        "schtask": [
            "/sc", "WEEKLY",
            "/d",  "MON,TUE,WED,THU,FRI",
            "/st", "15:45",
        ],
    },
    "InvestmentSim_Crypto": {
        "mode":    "crypto",
        "desc":    "Speculator crypto-only — every 4 hours 24/7",
        "log":     os.path.join(LOG_DIR, "crypto.log"),
        "schtask": [
            "/sc", "HOURLY",
            "/mo", "4",
            "/st", "00:00",
        ],
    },
}


def _make_action(mode: str, log: str) -> str:
    return f'"{PYTHON}" "{RUNNER}" --mode {mode} >> "{log}" 2>&1'


def install():
    os.makedirs(LOG_DIR, exist_ok=True)
    success = 0
    for task_name, cfg in TASKS.items():
        # Remove existing silently
        subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"],
                       capture_output=True)
        action = _make_action(cfg["mode"], cfg["log"])
        result = subprocess.run(
            ["schtasks", "/create",
             "/tn", task_name,
             "/tr", action,
             "/rl", "HIGHEST",
             "/f"] + cfg["schtask"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"  ✅ {task_name}")
            print(f"     {cfg['desc']}")
            success += 1
        else:
            print(f"  ❌ {task_name}: {result.stderr.strip()}")

    if success < len(TASKS):
        print("\n⚠️  Some tasks failed. Run this script as Administrator.")
    else:
        print(f"\n✅ All {success} tasks installed.")
        print("   Schedule summary:")
        print("   09:00 Mon-Fri  → InvestmentSim_Morning   (all 6 agents)")
        print("   15:45 Mon-Fri  → InvestmentSim_Afternoon (Speculator + Emotional)")
        print("   every 4 hours  → InvestmentSim_Crypto    (Speculator crypto-only)")


def remove():
    for task_name in TASKS:
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"  ✅ Removed: {task_name}")
        else:
            print(f"  ⚠️  Not found: {task_name}")


def status():
    for task_name in TASKS:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", task_name, "/fo", "LIST"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            # Pull out the key lines
            for line in result.stdout.splitlines():
                if any(k in line for k in ("TaskName", "Status", "Next Run", "Last Run")):
                    print(f"  {line.strip()}")
            print()
        else:
            print(f"  {task_name}: NOT INSTALLED\n")


def run_now(mode: str = "morning"):
    task_map = {cfg["mode"]: name for name, cfg in TASKS.items()}
    task_name = task_map.get(mode)
    if task_name:
        result = subprocess.run(
            ["schtasks", "/run", "/tn", task_name],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"✅ Triggered: {task_name}")
            return
    # Fallback: run directly
    print(f"Running {mode} mode directly...")
    os.system(f'"{PYTHON}" "{RUNNER}" --mode {mode}')


COMMANDS = {
    "install": lambda: install(),
    "remove":  lambda: remove(),
    "status":  lambda: status(),
    "run-now": lambda: run_now(sys.argv[2] if len(sys.argv) > 2 else "morning"),
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"Usage: python setup_scheduler.py [{' | '.join(COMMANDS)}]")
        print("       python setup_scheduler.py run-now [morning|afternoon|crypto]")
