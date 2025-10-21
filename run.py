import network
import time
import subprocess
from mininet.node import RemoteController, OVSSwitch


if __name__ == "__main__":
    time.sleep(2)
    network.setup(ctrl_port=6653)
    print("bye")