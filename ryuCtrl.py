from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
import networkx as nx

PRIO_MISS = 0
PRIO_LLDP = 1000

class ryuCtrl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(RyuCtrl, self).__init__(*args, **kwargs)
        self.G = nx.Graph()
    
    @set_ev_cls(event.EventLinkAdd)
    def update_topo(self, ev):
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

        src, dst = eth.src, eth.dst
        self.logger.info("PacketIn on s%s:%s  %s -> %s", dp.id, in_port, src, dst)

        # super dumb: flood (careful: will loop in meshy topologies)
        actions = [p.OFPActionOutput(ofp.OFPP_FLOOD)]
        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        out = p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                             in_port=in_port, actions=actions, data=data)
        dp.send_msg(out)
