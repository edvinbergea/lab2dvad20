from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from ryu.topology import event
import networkx as nx
import itertools
from ryu.topology.api import get_link, get_switch

PRIO_MISS = 0
PRIO_LLDP = 1000

agg_switches = {}
edge_switches = {}

class ryuCtrl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.G = nx.Graph()
        self.flows = []
        self.mac_to_dp = {}
        self.dp_to_cycle = {}
        self.dp_paths = {}
    
    @set_ev_cls(event.EventLinkAdd)
    def update_topo(self, ev):
        self.links_added += 1
        self.logger.info("Hello link")
        link = ev.link
        src = link.src
        dst = link.dst

        src_dpid = src.dpid
        dst_dpid = dst.dpid
        src_port = src.port_no
        dst_port = dst.port_no

        if src_dpid not in self.G:
            self.G.add_node(src_dpid)
        if dst_dpid not in self.G:
            self.G.add_node(dst_dpid)

        self.G.add_edge(
            src_dpid, dst_dpid,
            src_port=src_port,
            dst_port=dst_port
        )
        for switch in self.G.nodes:
            for neighbor in self.G.neighbors(s)
                self.dp_paths[s] = 

    def _find_paths(src, dst):
        return list(nx.all_shortest_paths(self.G, src, dst))
    
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        print(f"Switch connected: {dp.id}")
        ofp, p = dp.ofproto, dp.ofproto_parser
        
        actions = [p.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]

        match_all = p.OFPMatch()
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIO_MISS, match=match_all, instructions=inst))

        match_lldp = p.OFPMatch(eth_type=0x88cc)
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIO_LLDP, match=match_lldp, instructions=inst))


    def _update_cycles(paths):


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, p = dp.ofproto, dp.ofproto_parser
        in_port = msg.match.get('in_port')

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if not eth:
            return
        if eth.ethertype == 0x88cc:
            return  # ignore LLDP
        if eth.ethertype == 0x86DD:  # IPv6
            return

        src, dst = eth.src, eth.dst
        self.logger.info("PacketIn on s%s:%s  %s -> %s: Type = %s", dp.id, in_port, src, dst, eth.ethertype)
        
        if

        if dpid not in self.mac_to_dp[src]:
            self.mac_to_dp[src] = dpid
        
        flow = (src, dst)
        if flow not in self.flows:
            if 
            self.flows.append((src, dst))
            try:
                paths = self._find_paths(dpid, self.mac_to_dp[dst])
                self._update_cycles(dp, paths)
            except:
                return
        
            if not self.dp_to_cycle[dpid]
                self.dp_to_cycle[dpid] = itertools.cycle(self._find_paths(dpid, self.mac_to_dp[dst]))
            path = next(self.dp_to_cycle[dpid])
            i = path.index(dpid)
            nxt = path[i + 1]
            next_port = self.G[dpid][nxt]['src_port']

            actions = [p.OFPActionOutput(next_port)]
            inst = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
            match = p.OFPMatch(eth_src=src, eth_dst=dst)
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIO_MISS, match=match, instructions=inst))
        else:


