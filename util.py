import time as time
import random
import bisect
import os
import json
import asyncio
import statistics
import math


def getBytes(ttype):
    prob = random.random()
    xs = [p[0] for p in (web_eCDF if ttype == 1 else data_eCDF)]
    ys = [p[1] for p in (web_eCDF if ttype == 1 else data_eCDF)]

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


async def runIperf(source, cmd, tmo=20):
    start_time = time.monotonic()
    p = source.popen(cmd + " >/dev/null 2>&1")
    try:
        await asyncio.wait_for(asyncio.to_thread(p.wait), timeout=tmo)
        ct = time.monotonic() - start_time
        return ct
    except asyncio.TimeoutError:
        print("An iperf flow timed out!")
        try:
            p.terminate()
        except Exception:
            pass
        return math.nan


async def startServers(hd, start_port=5001, n_ports=8, tmo=10):
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


async def genDCTraffic(source, sink, ttype, flow_rate, t):
    hs, hd = self.net.get(source, sink)

    for h in (hs, hd):
        h.cmd('pkill -9 iperf iperf3 || true')

    hs.cmd(f"ping -c1 -W1 {hd.IP()} >/dev/null 2>&1") 
    hd.cmd(f"ping -c1 -W1 {hs.IP()} >/dev/null 2>&1")

    servers, port_pool = await self.startServers(hd)
    n_ports = len(port_pool)

    flows = []
    period = 1.0 / flow_rate
    clock = time.monotonic()
    deadline = clock + t

    i = 0
    while clock < deadline:
        size = self.getBytes(ttype)
        port = port_pool[(i % n_ports)-1] 
        cport = 40000 + (i % 20000)
        cmd = f'iperf -c {hd.IP()} -p {port} -L {cport} -n {size} -N -y C'
        jitter = random.uniform(0, 0.003)
        await asyncio.sleep(max(0.0, clock - time.monotonic()) + jitter)
        flows.append(asyncio.create_task(self.runIperf(hs, cmd)))
        clock += period
        i += 1

    res = await asyncio.gather(*flows)
    for srv in servers:
        srv.terminate()
    return res


def test_dc(net):
