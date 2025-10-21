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


NUM_SWITCHES = 20
PRIO_LLDP = 1000
PRIO_BALANCED = 500
PRIO_NORMAL = 100
PRIO_DEFAULT = 50
PRIO_MISS = 0


class RyuCtrl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(RyuCtrl, self).__init__(*args, **kwargs)
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
        print(f"num of switches linked: {self.seen_switches}")
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
        ae_switches = [s for s in G.nodes if deg[s] < maxdeg]

        # 4) Distance to nearest core
        dist = {n: math.inf for n in G.nodes}
        ms = {}
        for c in cores:
            for node, d in nx.single_source_shortest_path_length(G, c).items():
                ms[node] = min(ms.get(node, math.inf), d)
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

        self._install_layer_rules(cores, ae_switches)

        self.topo_done = True

    def _install_layer_rules(self, cores, ae_switches):
        for c in cores:
            dp = self.dp_by_id[c]
            ofp = dp.ofproto
            p = dp.ofproto_parser
            actions_c = [p.OFPActionOutput(ofp.OFPP_FLOOD)]
            inst_c = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions_c)]
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIO_DEFAULT, match=p.OFPMatch(), instructions=inst_c))

        for sw_id in ae_switches:
            dp = self.dp_by_id.get(sw_id)
            ofp = dp.ofproto
            parser = dp.ofproto_parser

            down_ports = self.downlink_ports.get(sw_id, set())

            for in_p in down_ports:
                out_actions = [parser.OFPActionOutput(out_p) for out_p in down_ports if out_p != in_p]
                out_actions.append(parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER))

                inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, out_actions)]
                mod = parser.OFPFlowMod(datapath=dp, priority=PRIO_DEFAULT,
                                        match=parser.OFPMatch(in_port=in_p),
                                        instructions=inst)
                dp.send_msg(mod)



    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        print(f"Switch connected: {dp.id}")
        ofp = dp.ofproto
        p   = dp.ofproto_parser
        
        actions = [p.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]

        match_all = p.OFPMatch()
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIO_MISS, match=match_all, instructions=inst))

        match_lldp = p.OFPMatch(eth_type=0x88cc)
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIO_LLDP, match=match_lldp, instructions=inst))

        self.mac_to_port[dp.id] = {}
        self.dp_by_id[dp.id] = dp


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        if not self.topo_done:
            print("blocking, topo not ready...")
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
        print(f"{src} contacting {dst}")

        # Ignore LLDP
        if eth.ethertype == 0x88cc:
            return

        self._learn_stuff(dp, in_port, src)

        if in_port in self.downlink_ports.get(dpid, set()):
            self._packet_in_upstream(dp, in_port, msg, src, dst)
        else:
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
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIO_BALANCED,
                                match=match, instructions=inst, idle_timeout=60))
        self._packet_out(dp, msg, in_port, actions)


    def _packet_out(self, dp, msg, in_port, actions):
        ofp, p = dp.ofproto, dp.ofproto_parser
        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                               in_port=in_port, actions=actions, data=data))

    def _learn_stuff(self, dp, in_port, src_mac):
        ofp, p = dp.ofproto, dp.ofproto_parser

        match = p.OFPMatch(eth_dst=src_mac)
        actions = [p.OFPActionOutput(in_port)]
        inst = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIO_NORMAL,
                                match=match, instructions=inst))

    
    def _rr_load_balance(self, dpid, dst, in_port):
        uplinks = sorted(self.uplink_ports.get(dpid, set()))

        if not uplinks:
            self.logger.warning(f"Probably in core")
            return self.dp_by_id[dpid].ofproto.OFPP_FLOOD

        if dpid not in self.rr_cycles:
            self.rr_cycles[dpid] = itertools.cycle(uplinks)

        return next(self.rr_cycles[dpid])
            

