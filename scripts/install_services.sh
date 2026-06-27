#!/usr/bin/env bash
# =====================================================================
# Trading & Research Command Center — macOS auto-start (launchd).
#
# Installs user LaunchAgents so the worker SCHEDULER and the control API
# start at login and restart if they crash — no terminal needed. A third
# (optional) agent serves the already-built dashboard so the browser just
# works. Idempotent: re-run any time.
#
# READ-ONLY app: these services analyse/validate and serve the dashboard —
# they place NO orders. NO secrets are written into the plists; the worker
# loads them from the repo .env at runtime (keep .env out of git).
#
# Usage:
#   bash scripts/install_services.sh              # scheduler + api + dashboard
#   WITH_DASHBOARD=0 bash scripts/install_services.sh   # only scheduler + api
# =====================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKER_DIR="$REPO_DIR/worker"
DASH_DIR="$REPO_DIR/dashboard"
VENV_PY="$WORKER_DIR/.venv/bin/python"
LOG_DIR="$REPO_DIR/logs"
LA_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"
PREFIX="com.tradingcommandcenter"
WITH_DASHBOARD="${WITH_DASHBOARD:-1}"
DASH_PORT="${DASH_PORT:-5273}"

echo "Repo:    $REPO_DIR"
echo "Worker:  $WORKER_DIR"
echo "Python:  $VENV_PY"

[ -x "$VENV_PY" ] || { echo "ERROR: venv python not found at $VENV_PY"; echo "Create it first (python -m venv worker/.venv && pip install -r worker/requirements.txt)"; exit 1; }
[ -f "$REPO_DIR/.env" ] || echo "WARNING: $REPO_DIR/.env not found — the worker needs it for Supabase/keys."
mkdir -p "$LOG_DIR" "$LA_DIR"

# write_plist <label-suffix> <workdir> <log-basename> <arg...>
write_plist() {
  local suffix="$1" workdir="$2" logname="$3"; shift 3
  local label="$PREFIX.$suffix"
  local plist="$LA_DIR/$label.plist"
  {
    echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    echo '<plist version="1.0"><dict>'
    echo "  <key>Label</key><string>$label</string>"
    echo '  <key>ProgramArguments</key><array>'
    for a in "$@"; do echo "    <string>$a</string>"; done
    echo '  </array>'
    echo "  <key>WorkingDirectory</key><string>$workdir</string>"
    echo '  <key>RunAtLoad</key><true/>'
    echo '  <key>KeepAlive</key><true/>'
    echo '  <key>ProcessType</key><string>Background</string>'
    echo "  <key>StandardOutPath</key><string>$LOG_DIR/$logname.out.log</string>"
    echo "  <key>StandardErrorPath</key><string>$LOG_DIR/$logname.err.log</string>"
    echo '</dict></plist>'
  } > "$plist"

  # (Re)load idempotently: bootout if present, then bootstrap + start now.
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$plist"
  launchctl enable "gui/$UID_NUM/$label"
  launchctl kickstart -k "gui/$UID_NUM/$label" 2>/dev/null || true
  echo "installed + started: $label"
}

# 1) worker scheduler (APScheduler loop: prices/news/briefings/decision/etc.)
write_plist "scheduler" "$WORKER_DIR" "scheduler" "$VENV_PY" "-m" "app.main" "run"

# 2) control API (Aggiorna /refresh + Genera analisi AI /decision/{sym}/ai)
write_plist "api" "$WORKER_DIR" "api" "$VENV_PY" "-m" "app.main" "api"

# 3) (optional) dashboard — serve the BUILT static app (no node at runtime)
if [ "$WITH_DASHBOARD" = "1" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "Building dashboard…"; ( cd "$DASH_DIR" && npm run build >/dev/null 2>&1 ) || echo "WARNING: dashboard build failed (will serve existing dist if present)."
  fi
  if [ -f "$DASH_DIR/dist/index.html" ]; then
    write_plist "dashboard" "$DASH_DIR" "dashboard" "$VENV_PY" "-m" "http.server" "$DASH_PORT" "--directory" "$DASH_DIR/dist"
    echo "dashboard served at http://localhost:$DASH_PORT/"
  else
    echo "SKIP dashboard agent: $DASH_DIR/dist not built (run 'npm run build' in dashboard/)."
  fi
else
  echo "WITH_DASHBOARD=0 -> dashboard agent not installed."
fi

echo
echo "Done. Verify:  launchctl list | grep $PREFIX"
echo "API health:    curl -s http://127.0.0.1:8787/health"
echo "Logs:          $LOG_DIR/"
echo "Uninstall:     bash scripts/uninstall_services.sh"
