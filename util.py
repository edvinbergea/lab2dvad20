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


async def runNetperf(source, sink_ip, size, tmo=40):
    """
    Run a single netperf TCP_STREAM test with specified bytes
    Returns completion time or nan on timeout
    """
    start_time = time.monotonic()
    
    # TCP_STREAM sends 'size' bytes in one direction
    # -H: target host, -l: test length (use -1 for size-based)
    # -- -m: message size (we'll send one message of 'size' bytes)
    cmd = f'netperf -H {sink_ip} -t TCP_STREAM -l -1 -- -m {size} -M {size}'
    
    p = source.popen(cmd + " >/dev/null 2>&1")
    try:
        await asyncio.wait_for(asyncio.to_thread(p.wait), timeout=tmo)
        ct = time.monotonic() - start_time
        return ct
    except asyncio.TimeoutError:
        print(f"A netperf flow timed out after {tmo}s!")
        try:
            p.terminate()
        except Exception:
            pass
        return math.nan


async def startNetserver(hd, tmo=10):
    """
    Start a single netserver daemon that handles all connections
    Much simpler than iperf's per-port approach
    """
    # Kill any existing netserver
    hd.cmd('pkill -9 netserver || true')
    
    # Start netserver (listens on port 12865 by default)
    server = hd.popen('netserver >/dev/null 2>&1')
    
    # Wait for netserver to be ready
    deadline = time.monotonic() + tmo
    while time.monotonic() < deadline:
        out = hd.cmd("ss -ltn")
        if ":12865 " in out or ":12865\n" in out:
            return server
        await asyncio.sleep(0.5)
    
    raise RuntimeError("Failed to start netserver")


async def genDCTraffic(net, source, sink, ttype, flow_rate, t, config):
    hs, hd = net.get(source, sink)
    
    # Clean up any existing processes
    for h in (hs, hd):
        h.cmd('pkill -9 netperf netserver || true')
    
    # Verify connectivity
    ping_result = hs.cmd(f"ping -c1 -W1 {hd.IP()}")
    if "1 received" not in ping_result:
        print(f"Warning: Ping failed from {source} to {sink}")
    
    # Start single netserver (much simpler than iperf port pool!)
    try:
        server = await startNetserver(hd)
    except RuntimeError as e:
        print(f"Failed to start netserver: {e}")
        return [math.nan] * int(flow_rate * t)
    
    flows = []
    period = 1.0 / flow_rate
    next_flow_time = time.monotonic()
    deadline = next_flow_time + t
    
    try:
        i = 0
        while next_flow_time < deadline:
            size = getBytes(ttype, config)
            
            jitter = random.uniform(0, 0.003)
            sleep_time = max(0.0, next_flow_time - time.monotonic()) + jitter
            await asyncio.sleep(sleep_time)
            
            flows.append(asyncio.create_task(runNetperf(hs, hd.IP(), size)))
            next_flow_time += period
            i += 1
        
        res = await asyncio.gather(*flows, return_exceptions=True)
        
        # Filter out exceptions
        results = []
        for r in res:
            if isinstance(r, Exception):
                print(f"Flow failed: {r}")
                results.append(math.nan)
            else:
                results.append(r)
        
        return results
    finally:
        try:
            server.terminate()
        except Exception:
            pass


def open_config():
    with open("config.json", "r") as f:
        return json.load(f)


def open_saved():
    with open("saved.json", "r") as f:
        return json.load(f)


def getHostsRandom(config):
    return [f"h{n}" for n in random.sample(range(*config["host_range"]), 2)]


def test_dc(net):
    config = open_config()
    progress = 0
    amount_of_tests = config["repetitions"] * (config["flow_rate_range"][1] - config["flow_rate_range"][0])
    results = []
    
    for _ in range(config["repetitions"]):
        results_flow_rates = []
        for flow_rate in range(*config["flow_rate_range"]):
            source, sink = getHostsRandom(config)
            results_flow_rates.append(
                asyncio.run(genDCTraffic(net, source, sink, config["traffic_type"], 
                                        flow_rate, config["test_time"], config))
            )
            progress += 1
            print(f"Progress: {progress}/{amount_of_tests}")
        results.append(results_flow_rates)
    
    return results