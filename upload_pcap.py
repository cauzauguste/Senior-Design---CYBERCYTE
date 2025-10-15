import os
import datetime
from firebase_admin import credentials, firestore, initialize_app
from dotenv import load_dotenv

load_dotenv()
key_path = os.getenv("FIREBASE_KEY_PATH")

cred = credentials.Certificate(key_path)
initialize_app(cred)
db = firestore.client()

def upload_pcap_metadata(pcap_path, source="Wireshark"):
    if not os.path.exists(pcap_path):
        print(f"[ERROR] File not found: {pcap_path}")
        return

    file_stats = os.stat(pcap_path)
    file_size_kb = round(file_stats.st_size / 1024, 2)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data = {
        "file_name": os.path.basename(pcap_path),
        "file_size_kb": file_size_kb,
        "source": source,
        "timestamp": timestamp,
        "status": "uploaded",
        "uploaded_by": "Mikala",
    }

    db.collection("pcaps").add(data)
    print(f"[SUCCESS] Uploaded metadata for {pcap_path} to Firestore.")

if __name__ == "__main__":
    pcap_file = "sample_capture.pcap"
    upload_pcap_metadata(pcap_file)
