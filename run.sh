#!/bin/bash
set -e

# Start Ryu controller in background and log all output
echo "[+] Starting Ryu controller..."
ryu-manager --ofp-tcp-listen-port 6653 ryuCtrl.py > ryu.log 2>&1 &
RYU_PID=$!
echo "[+] Ryu started with PID $RYU_PID (logging to ryu.log)"

# Run your Mininet script (in current terminal)
echo "[+] Running Mininet script (main.py)..."
sudo python3 main.py

# When Mininet finishes or is interrupted, kill Ryu
echo "[+] Cleaning up..."
sudo mn -c
echo "[+] Done."
