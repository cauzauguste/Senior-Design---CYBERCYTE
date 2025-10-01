             
import firebase_admin
from firebase_admin import credentials, firestore

# Path to your Firebase service account key on the VM
cred = credentials.Certificate("/home/mikalamitchell72/app/firebase_key.json")
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

# Add a test document to the 'pcaps' collection
doc_ref = db.collection("pcaps").document("capture1")
doc_ref.set({
    "source": "Wireshark",
    "uploaded_by": "Mikala",
    "timestamp": "2025-09-29",
    "status": "pending"
})

print("Current documents in 'pcaps':")
#This script is a connection test: it logs into your Firestore database from your VM using the service-account key and writes a sample document (capture1 in pcaps) to make sure everything works.
#need the Firebase test code so you’re sure your VM can authenticate to Firestore and read/write PCAP data
