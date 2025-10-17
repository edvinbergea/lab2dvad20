import network
import time
import subprocess
from mininet.node import RemoteController, OVSSwitch


if __name__ == "__main__":
    '''
    ryu_proc = subprocess.Popen(
        ["ryu-manager", "--ofp-tcp-listen-port", "6653", "ryuController.py"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    '''
    time.sleep(2)
    network.setup(ctrl_port=6653)
    print("bye")
    #ryu_proc.terminate()