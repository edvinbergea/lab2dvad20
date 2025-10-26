#!/bin/bash
set -e

echo "[+] Starting Ryu controller..."
ryu-manager --ofp-tcp-listen-port 6653 ryuCtrl.py > ryu.log 2>&1 &
RYU_PID=$!
echo "Ryu started with PID $RYU_PID (logging to ryu.log)"

echo "Running Mininet script (main.py)..."
sudo python3 main.py

echo "Cleaning up..."
sudo mn -c > /dev/null 2>&1 || true
echo "Done."
