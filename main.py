from network import setup
from util import test_dc
import analyze
import time
import sys


if __name__ == "__main__":
    time.sleep(5)
    net = setup(ctrl_port=6653)
    res = test_dc(net)
    analyze.analyze(res)
    print("Bye")