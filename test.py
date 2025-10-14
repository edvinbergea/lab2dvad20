#!/usr/bin/env python3
import os
import sys
import time
import shlex
import subprocess
import argparse
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo

class SimpleTopo(Topo):
    def build(self):
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        s1 = self.addSwitch('s1')
        self.addLink(h1, s1)
        self.addLink(h2, s1)

def start_ryu():
    # Prefer an explicit interpreter from env (set RYU_PYTHON=$(which python) in your conda env)
    ryu_py = os.environ.get("RYU_PYTHON", sys.executable)
    cmd = [ryu_py, "-m", "ryu.cmd.manager", "ryu.app.simple_switch_13"]
    print(f"[+] Starting Ryu with: {' '.join(shlex.quote(c) for c in cmd)}")
    # Start detached; don't capture stdout/stderr to avoid blocking
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)
    return proc

def main(spawn_controller: bool):
    ryu_proc = None
    try:
        if spawn_controller:
            ryu_proc = start_ryu()
        else:
            print("[+] Assuming ryu-manager is already running on 127.0.0.1:6633")

        print("[+] Starting Mininet with remote controller...")
        topo = SimpleTopo()
        net = Mininet(topo=topo, switch=OVSSwitch, controller=None, build=True)
        c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)
        net.start()

        print("[+] Testing connectivity (pingAll)...")
        loss = net.pingAll()
        print(f"[+] Ping result: {loss}% packet loss")
    finally:
        print("[+] Cleaning up Mininet...")
        try:
            net.stop()
        except Exception:
            pass
        if ryu_proc:
            print("[+] Terminating Ryu...")
            ryu_proc.terminate()
            # Best effort wait
            try:
                ryu_proc.wait(timeout=3)
            except Exception:
                ryu_proc.kill()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-spawn", action="store_true",
                        help="Do not spawn ryu; assume it is already running.")
    args = parser.parse_args()
    main(spawn_controller=not args.no_spawn)
