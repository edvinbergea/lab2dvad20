# simple_sp_routing.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
import math
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.topology import event
from ryu.topology.api import get_link, get_switch
import networkx as nx
import itertools
from ryu.base.app_manager import require_app
require_app('ryu.topology.switches')


PRIO_MISS = 0
PRIO_LLDP = 1000
PRIO_UPLINK_NORMAL = 50
PRIO_HOST_FLOWS = 100
IDLE_TIMEOUT = 60
HARD_TIMEOUT = 0
NUM_SWITCHES = 20


class RyuCtrl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.dp_by_id = {}
        self.rr_cycles = {}
        self.uplink_ports = {}
        self.downlink_ports = {}
        self.G = nx.Graph()
        self.seen_switches = 0
        self.topo_done = False


    @set_ev_cls(event.EventSwitchEnter)
    def topo_update(self, ev):
        self.seen_switches += 1
        if self.seen_switches < NUM_SWITCHES:
            return

        # 1) Build switch graph
        switches = get_switch(self, None)
        links = get_link(self, None)

        G = nx.Graph()
        for s in switches:
            G.add_node(s.dp.id, ports=s.ports)
        for l in links:
            G.add_edge(l.src.dpid, l.dst.dpid,
                    src_port=l.src.port_no, dst_port=l.dst.port_no)
        self.G = G

        # 2) Init up ports and down ports
        self.uplink_ports   = {s.dp.id: set() for s in switches}
        self.downlink_ports = {s.dp.id: set() for s in switches}

        # 3) Pick out likely cores
        deg = dict(G.degree())
        maxdeg = max(deg.values())
        cores = [n for n in G.nodes if deg[n] == maxdeg]
        agg_switches = [s for s in G.nodes if deg[s] == maxdeg-1]
        edge_switches = [s for s in G.nodes if deg[s] == maxdeg-2]

        # 4) Distance to nearest core
        dist = {n: math.inf for n in G.nodes}
        ms = nx.multi_source_shortest_path_length(G, sources=cores)
        dist.update(ms)

        # 5) Classify up and down ports per switch
        for u in G.nodes:
            du = dist.get(u)
            for v in G.neighbors(u):
                dv = dist.get(v)
                e = G[u][v]
                if dv < du:
                    self.uplink_ports[u].add(e['src_port'])
                else:
                    self.downlink_ports[u].add(e['src_port'])

        self._install_layer_rules(cores, agg_switches, edge_switches)

        self.topo_done = True

    def _install_layer_rules(cores, agg_switches, edge_switches):   
        for c in cores:
            dp = self.dp_by_id[c]
            ofp = dp.ofproto
            p = dp.ofproto_parser
            actions_c = [p.OFPActionOutput(ofproto.OFPP_FLOOD)]
            inst_c = [p.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions_c)]
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=10, match=p.OFPMatch(), instructions=inst_c)
        
        for s in agg_switches + edge_switches:
            dp = self.dp_by_id[s]
            ofp = dp.ofproto
            p = dp.ofproto_parser
            actions_ae = [p.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
            down_ports = self.downlink_ports.get(s)
            for port in down_ports:
                added_actions = [parser.OFPActionOutput(po) for po in [p for p in down_ports if p != port]]
                inst_ae = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions_ae + added_actions)]
                s.send_msg(p.OFPFlowMod(datapath=a, priority=10, match=p.OFPMatch(in_port=port), instructions=inst_ae)


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        ofp = dp.ofproto
        p   = dp.ofproto_parser
        
        actions = [p.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]

        match_all = p.OFPMatch()
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=0, match=match_all, instructions=inst))

        match_lldp = p.OFPMatch(eth_type=0x88cc)
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=1000, match=match_lldp, instructions=inst))

        self.mac_to_port[dp.id] = {}
        self.dp_by_id[dp.id] = dp


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        if not topo_done:
            return

        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        p = dp.ofproto_parser
        in_port = msg.match['in_port']
        dpid = dp.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        src = eth.src; dst = eth.dst

        # Ignore LLDP
        if eth.ethertype == 0x88cc:
            return

        if in_port in self.downlink_ports_ports.get(dpid, set()):
            self._packet_in_upstream(dp, in_port, msg, src, dst)
        elif in_port in self.uplink_ports.get(dpid, set()):
            self._packet_in_downstream(dp, in_port, msg, src, dst)
        else:
            pass

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            actions = [p.OFPActionOutput(out_port)]
            match = p.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=100,
                                    match=match,
                                    instructions=[p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)],
                                    idle_timeout=60))
            self._packet_out(dp, msg, in_port, actions)
            return

    # --- helpers ---
    
    def _packet_in_upstream(self, dp, in_port, msg, src, dst):
        ofp = dp.ofproto
        p = dp.ofproto_parser
        dpid = dp.id

        next_port = self._rr_load_balance(dpid, dst, in_port)
        match = p.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)
        actions = [p.OFPActionOutput(next_port)]
        inst = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=100, match=match, instructions=inst, idle_timeout=60)
        self._packet_out(dp, msg, in_port, actions)

    def _packet_in_downstream(self, dp, in_port, msg, src, dst):
        ofp = dp.ofproto
        p = dp.ofproto_parser
        dpid = dp.id

        self.mac_to_port.setdefault(dpid, {})[src] = in_port

    def _packet_out(self, dp, msg, in_port, actions):
        ofp, p = dp.ofproto, dp.ofproto_parser
        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                               in_port=in_port, actions=actions, data=data))

    
    def _rr_load_balance(self, dpid, dst, in_port):
        uplinks = sorted(self.uplink_ports.get(dpid, set()))

        if not uplinks:
            self.logger.warning(f"Probably in core")
            return self.dp_by_id[dpid].ofproto.OFPP_FLOOD

        if dpid not in self.rr_cycles:
            self.rr_cycles[dpid] = itertools.cycle(uplinks)

        return next(self.rr_cycles[dpid])
            

