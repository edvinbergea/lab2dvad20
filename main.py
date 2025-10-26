from network import setup, clean_up
from util import test_dc
import analyze
import time
import sys


if __name__ == "__main__":
    time.sleep(5)
    net = setup(ctrl_port=6653)
    res = test_dc(net)
    clean_up(net)
    analyzed_res = analyze.analyze(res)
    analyze.save_results(analyzed_res)
    analyze.display_results(analyzed_res)
    print("Bye")