from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from itertools import cycle
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.node import Controller
from functools import partial


class FatTree(Topo):
    def build(self):
        # Switches & Hosts
        core  = [self.addSwitch(f"s{i}") for i in range(4)]          # s0..s3
        aggs  = [self.addSwitch(f"s{i}") for i in range(4, 12)]      # s4..s11 (pods of 2)
        edges = [self.addSwitch(f"s{i}") for i in range(12, 20)]     # s12..s19 (pods of 2)
        hosts = [self.addHost(f"h{i}") for i in range(16)]           # h0..h15 (2 per edge)

        # Aggregation <-> Core
        agg_core_links = [
            self.addLink(a, c)
            for ai, a in enumerate(aggs)
            for c in core[(ai % 2) * 2 : (ai % 2) * 2 + 2]]
        # Edge <-> Aggregation
        edge_agg_links = [
            self.addLink(e, a)
            for ei, e in enumerate(edges)
            for a in aggs[(ei // 2) * 2 : (ei // 2) * 2 + 2]]
        # Host <-> Edge
        host_edge_links = [
            self.addLink(h, e)
            for ei, e in enumerate(edges)
            for h in hosts[ei * 2 : (ei + 1) * 2]]


def setup(ctrl_port=6653):
    topo = FatTree()
    switch = partial(OVSSwitch, protocols='OpenFlow13', failMode='secure')
    net = Mininet(topo=topo, switch=switch, link=TCLink, controller=None, autoSetMacs=True, autoStaticArp=False)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=ctrl_port)
    net.start()
    CLI(net)
    