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
UP = 1
DOWN = 0

S1, S2, S3, S4 = 1, 2, 3, 4
PORTS = {
    1: {  # S1
        2: 1,   # to S2
        4: 2,   # to S4
    },
    2: {  # S2
        1: 1,   # to S1
        3: 2,   # to S3
    },
    3: {  # S3
        2: 1,   # to S2
        4: 2,   # to S4
    },
    4: {  # S4
        3: 2,   # to S3
        1: 1,   # to S1
    }
}

L2R_PATHS = [[2, 3, 4], [2, 1, 4]]
R2L_PATHS = [[4, 3, 2], [4, 1, 2]]

UP_PORTS = {
    1: [],
    2: [1, 2],
    3: [],
    4: [1, 2]
}
DOWN_PORTS = {
    1: [1, 2],
    2: [3, 4],
    3: [1, 2],
    4: [3, 4]
}

class ryuCtrl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dpid_to_dp = {}
        self.l2r_paths_cycle = itertools.cycle(L2R_PATHS)
        self.r2l_paths_cycle = itertools.cycle(R2L_PATHS)
        self.flows = []
        self.flow_to_path = {}


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

        self.dpid_to_dp[dp.id] = dp


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, p = dp.ofproto, dp.ofproto_parser
        dpid = dp.id
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

        flow = (src, dst)
        if flow not in self.flows:
            print(f"new flow: {flow}")
            self.flows.append(flow)
            self.flow_to_path[flow] = self._pick_path(dpid)
        
        direction = UP if in_port in DOWN_PORTS[dpid] else DOWN # 1 if up and 0 if down
        if direction == UP:
            path = self.flow_to_path[flow]
            print(f"path: {path} dpid: {dpid}")
            i = path.index(dpid)
            nxt_switch = path[i+1]
            print(f"next switch: {nxt_switch}")
            nxt_port = PORTS[dpid][nxt_switch]
            
            direction = 1 if in_port in UP_PORTS[dpid] else 0 # 1 if up and 0 if down

            if dpid == S1 or dpid == S3:    # In agg layer
                self._flood_down(dp, ofp, p, in_port, msg.data)
                #self._learn_edge_agg()
            else:                           # In edge layer
                self._flood_up_down(dp, ofp, p, in_port, nxt_port, msg.data)
                #self._learn_host_edge()
        else:
            self._flood_down(dp, ofp, p, in_port, msg.data)
            #self._learn_agg_edge()


    def _pick_path(self, dpid):
        if dpid == S2:
            return next(self.l2r_paths_cycle)
        elif dpid == S4:
            return next(self.r2l_paths_cycle)

    def _flood_up_down(self, dp, ofp, p, in_port, nxt_port, data):
        ports = DOWN_PORTS[dp.id]
        actions = [p.OFPActionOutput(port) for port in ports if not port == in_port]
        dp.send_msg(p.OFPPacketOut(in_port=in_port, datapath=dp, actions=actions, buffer_id=ofp.OFP_NO_BUFFER, data=data))
        print(f"in here: {nxt_port} {ports}")
        actions = [p.OFPActionOutput(nxt_port)]
        dp.send_msg(p.OFPPacketOut(in_port=in_port, datapath=dp, actions=actions, buffer_id=ofp.OFP_NO_BUFFER, data=data))
    
    def _flood_down(self, dp, ofp, p, in_port, data):
        print("flooding")
        ports = DOWN_PORTS[dp.id]
        actions = [p.OFPActionOutput(port) for port in ports]
        dp.send_msg(p.OFPPacketOut(in_port=in_port, datapath=dp, actions=actions, buffer_id=ofp.OFP_NO_BUFFER, data=data))
  
        


