from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd
from scapy.all import rdpcap, IP, TCP, UDP, ICMP
from datetime import datetime
from collections import defaultdict
import io
#template
app = FastAPI()

@app.post("/analyze-pcap/")
async def analyze_pcap(file: UploadFile = File(...)):
    try:
        # Read the uploaded file into memory
        contents = await file.read()
        with open("temp.pcap", "wb") as f:
            f.write(contents)

        # Load packets
        packets = rdpcap("temp.pcap")

        # Dictionary to hold flows: key = (src_ip, dst_ip, src_port, dst_port, proto)
        flows = defaultdict(lambda: {
            "src_ip": None,
            "dst_ip": None,
            "src_port": None,
            "dst_port": None,
            "protocol": None,
            "timestamps": [],
            "size": 0
        })

        for pkt in packets:
            try:
                if IP in pkt:
                    src_ip = pkt[IP].src
                    dst_ip = pkt[IP].dst
                    proto = pkt[IP].proto
                else:
                    continue  # skip if no IP layer

                src_port, dst_port = None, None
                if TCP in pkt:
                    src_port = pkt[TCP].sport
                    dst_port = pkt[TCP].dport
                    proto_name = "TCP"
                elif UDP in pkt:
                    src_port = pkt[UDP].sport
                    dst_port = pkt[UDP].dport
                    proto_name = "UDP"
                elif ICMP in pkt:
                    proto_name = "ICMP"
                else:
                    proto_name = str(proto)

                # Define 5-tuple key
                key = (src_ip, dst_ip, src_port, dst_port, proto_name)

                # Update flow
                flow = flows[key]
                flow["src_ip"] = src_ip
                flow["dst_ip"] = dst_ip
                flow["src_port"] = src_port
                flow["dst_port"] = dst_port
                flow["protocol"] = proto_name
                flow["timestamps"].append(pkt.time)
                flow["size"] += 1

            except Exception as e:
                print(f"Error parsing packet: {e}")
                continue

        # Convert flows to list of dicts
        flow_list = []
        for key, flow in flows.items():
            timestamps = flow["timestamps"]
            duration = (max(timestamps) - min(timestamps)) if len(timestamps) > 1 else 0
            flow_list.append({
                "src_ip": flow["src_ip"],
                "dst_ip": flow["dst_ip"],
                "src_port": flow["src_port"],
                "dst_port": flow["dst_port"],
                "protocol": flow["protocol"],
                "timestamp_first": datetime.fromtimestamp(min(timestamps)).isoformat(),
                "timestamp_last": datetime.fromtimestamp(max(timestamps)).isoformat(),
                "size": flow["size"],
                "duration": duration
            })

        # Convert to DataFrame
        df = pd.DataFrame(flow_list)

        # Save to CSV
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False)
        csv_buf.seek(0)

        return {
            "message": "PCAP analyzed successfully",
            "num_flows": len(df),
            "csv_preview": df.head().to_dict(orient="records")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing pcap: {str(e)}")
