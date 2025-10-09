import pandas as pd
from scapy.all import rdpcap, IP, TCP, UDP, ICMP
from collections import defaultdict
from datetime import datetime

def pcap_to_flows(file_path: str):
    packets = rdpcap(file_path)
    flows = defaultdict(lambda: {"timestamps": [], "size": 0})
    for pkt in packets:
        try:
            if IP not in pkt: continue
            src_ip, dst_ip = pkt[IP].src, pkt[IP].dst
            proto_name = "OTHER"
            src_port, dst_port = None, None
            if TCP in pkt:
                proto_name = "TCP"
                src_port, dst_port = pkt[TCP].sport, pkt[TCP].dport
            elif UDP in pkt:
                proto_name = "UDP"
                src_port, dst_port = pkt[UDP].sport, pkt[UDP].dport
            elif ICMP in pkt:
                proto_name = "ICMP"
            key = (src_ip, dst_ip, src_port, dst_port, proto_name)
            flow = flows[key]
            flow["timestamps"].append(pkt.time)
            flow["size"] += 1
        except Exception:
            continue

    flow_list = []
    for key, flow in flows.items():
        timestamps = flow["timestamps"]
        duration = (max(timestamps) - min(timestamps)) if timestamps else 0
        flow_list.append({
            "src_ip": key[0],
            "dst_ip": key[1],
            "src_port": key[2],
            "dst_port": key[3],
            "protocol": key[4],
            "timestamp_first": datetime.fromtimestamp(min(timestamps)).isoformat() if timestamps else None,
            "timestamp_last": datetime.fromtimestamp(max(timestamps)).isoformat() if timestamps else None,
            "size": flow["size"],
            "duration": duration
        })
    df = pd.DataFrame(flow_list)
    return df
