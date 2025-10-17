# simple_sp_routing.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.topology import event
from ryu.topology.api import get_link, get_switch
import networkx as nx


class RyuCtrl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        ofp = dp.ofproto
        p   = dp.ofproto_parser
        
        match = p.OFPMatch()  # matches everything
        actions = [p.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=0, match=match, instructions=inst))

        match = p.OFPMatch(eth_type=0x88cc)  # LLDP
        actions = [p.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        inst  = [p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=1000, match=match, instructions=inst))

        self.mac_to_port[dp.id] = {}
        self.dp_by_id[dp.id] = dp


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        p = dp.ofproto_parser
        in_port = msg.match['in_port']
        dpid = dp.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # Ignore LLDP
        if eth.ethertype == 0x88cc:
            return
        
        # Ignore if downstream
        if in_port in self.uplink_ports.get(dpid, set()):
        return

        src = eth.src; dst = eth.dst
        self.mac_to_port.setdefault(dpid, {})[src] = in_port

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

        next_port = self._rr_load_balance(dpid, dst, in_port)

        actions = [p.OFPActionOutput(next_port)]
        match = p.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=100,
                             match=match,
                             instructions=[p.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)],
                             idle_timeout=60))
        self._packet_out(dp, msg, in_port, actions)


    def _packet_out(self, dp, msg, in_port, actions):
        ofp, p = dp.ofproto, dp.ofproto_parser
        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                               in_port=in_port, actions=actions, data=data))

    # --- helpers ---
    def _rr_load_balance()

