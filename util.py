import time as time
import random
import bisect
import os
import json
import asyncio
import statistics
import math


def getBytes(ttype, config):
    prob = random.random()
    xs = [p[0] for p in (config["web_eCDF"] if ttype == 1 else config["data_eCDF"])]
    ys = [p[1] for p in (config["web_eCDF"] if ttype == 1 else config["data_eCDF"])]

    if prob <= ys[0]:
        x = xs[0]
    elif prob >= ys[-1]:
        x = xs[-1]
    else:
        i = bisect.bisect_left(ys, prob)
        x0, y0 = xs[i-1], ys[i-1]
        x1, y1 = xs[i], ys[i]
        k = (y1 - y0) / (x1 - x0)
        m = y0 - k * x0
        x = (prob - m) / k

    return math.ceil(x)


async def runIperf(source, cmd, tmo=5):
    start_time = time.monotonic()
    p = source.popen(cmd + " >/dev/null 2>&1")
    try:
        await asyncio.wait_for(asyncio.to_thread(p.wait), timeout=tmo)
        ct = time.monotonic() - start_time
        return ct 
    except asyncio.TimeoutError:
        print(f"An iperf flow timed out after {tmo}s!")
        try:
            p.terminate()
        except Exception:
            pass
        return math.nan


async def startServers(hd, start_port=5001, n_ports=8, tmo=20):
    port_pool = []
    servers = [hd.popen(f'iperf -s -p {start_port+i} >/dev/null 2>&1') for i in range(n_ports)]
    needed_ports = [port for port in range(start_port, start_port+n_ports)] 
    deadline = time.monotonic() + tmo
    while time.monotonic() < deadline:
        out = hd.cmd("ss -ltn")
        for port in list(needed_ports):
            if f":{port} " in out or f":{port}\n" in out:
                needed_ports.remove(port)
                port_pool.append(port)
        if not needed_ports:
            break
        await asyncio.sleep(1)
    return servers, port_pool


async def genDCTraffic(net, source, sink, ttype, flow_rate, t, config):
    hs, hd = net.get(source, sink)

    for h in (hs, hd):
        h.cmd('pkill -9 iperf iperf3 || true')

    hs.cmd(f"ping -c1 -W1 {hd.IP()} >/dev/null 2>&1") 
    hd.cmd(f"ping -c1 -W1 {hs.IP()} >/dev/null 2>&1")

    servers, port_pool = await startServers(hd)
    n_ports = len(port_pool)

    flows = []
    period = 1.0 / flow_rate
    next_flow_time = time.monotonic()
    deadline = next_flow_time + t

    i = 0
    while next_flow_time < deadline:
        size = getBytes(ttype, config)
        port = port_pool[i % n_ports]
        cport = 40000 + (i % 20000)
        cmd = f'iperf -c {hd.IP()} -p {port} -L {cport} -n {size} -N -y C'
        
        jitter = random.uniform(0, 0.003)
        sleep_time = max(0.0, next_flow_time - time.monotonic()) + jitter
        await asyncio.sleep(sleep_time)
        
        flows.append(asyncio.create_task(runIperf(hs, cmd)))
        next_flow_time += period 
        i += 1

    res = await asyncio.gather(*flows)
    for srv in servers:
        srv.terminate()
    return res


def open_config():
    with open("config.json", "r") as f:
        return json.load(f)
         

def open_saved():
    with open("saved.json", "r") as f:
        return json.load(f)


def getHosts(config):
    return [f"h{n}" for n in random.sample(range(*config["host_range"]), 2)]


def test_dc(net):
    config = open_config()
    progress = 0
    amount_of_tests = config["repetitions"] * (config["flow_rate_range"][1] - config["flow_rate_range"][0])
    results = []
    
    for rep in range(config["repetitions"]):
        results_flow_rates = []
        for flow_rate in range(*config["flow_rate_range"]):
            source, sink = getHosts(config)
            results_flow_rates.append(asyncio.run(genDCTraffic(net, source, sink, config["traffic_type"], flow_rate, config["test_time"], config)))
            progress += 1
            print(f"Progress: {progress}/{amount_of_tests}")
        results.append(results_flow_rates)
    
    return results