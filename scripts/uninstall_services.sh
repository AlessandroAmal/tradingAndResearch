#!/usr/bin/env bash
# =====================================================================
# Trading & Research Command Center — remove the macOS LaunchAgents.
# Stops and unloads the scheduler / api / dashboard agents and deletes
# their plists. Idempotent: safe to run even if nothing is installed.
# (Logs in logs/ and your .env are left untouched.)
# =====================================================================
set -euo pipefail

LA_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"
PREFIX="com.tradingcommandcenter"

for suffix in scheduler api dashboard; do
  label="$PREFIX.$suffix"
  plist="$LA_DIR/$label.plist"
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null && echo "stopped: $label" || echo "not running: $label"
  if [ -f "$plist" ]; then rm -f "$plist"; echo "removed:  $plist"; fi
done

echo "Done. Verify gone:  launchctl list | grep $PREFIX  (should print nothing)"
