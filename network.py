from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.cli import CLI
from functools import partial


class OnePod(Topo):
    def build(self):
        s1 = self.addSwitch(f"s1")
        s2 = self.addSwitch(f"s2")
        s3 = self.addSwitch(f"s3")
        s4 = self.addSwitch(f"s4")

        h1 = self.addHost(f"h1")
        h2 = self.addHost(f"h2")
        h3 = self.addHost(f"h3")
        h4 = self.addHost("h4")

        self.addLink(s1, s2)
        self.addLink(s1, s4)
        self.addLink(s2, s3)
        self.addLink(s2, s4)

        self.addLink(s3, h1)
        self.addLink(s3, h2)
        self.addLink(s4, h3)
        self.addLink(s4, h4)
        

def setup(ctrl_port=6653):
    topo = OnePod()
    switch = partial(OVSSwitch, protocols='OpenFlow13', failMode='secure')
    net = Mininet(topo=topo, switch=switch, link=TCLink,
                  controller=None, autoSetMacs=True, autoStaticArp=False)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=ctrl_port)
    net.start()
    net.waitConnected(timeout=5)   # <-- important
    CLI(net)
    net.stop()

    