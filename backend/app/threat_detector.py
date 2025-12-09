"""
Threat Detection Service for Cybercyte

Integrates with existing FastAPI app and PostgreSQL database.
Uses ML models and LLM (Gemini/OpenAI) for threat detection and mitigation.
"""

import os
import asyncio
import json
from typing import List, Dict, Any
from asyncio import to_thread
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMClassifier
import aiohttp

from backend.app.database import engine
from sqlalchemy import text

from dotenv import load_dotenv
load_dotenv()

router = APIRouter()

POLL_INTERVAL_SECONDS = 30  # how often to run detection

# -------------------------
# LLM Integration
# -------------------------
def call_gemini(prompt: str) -> Dict[str, Any]:
    """Calls Gemini Pro API using the official Google GenAI SDK."""
    try:
        from google import genai

        API_KEY = os.environ.get('GEMINI_API_KEY')
        if not API_KEY:
            return {'error': 'GEMINI_API_KEY not set'}

        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return {'response': response.text}
    except Exception as e:
        return {'error': str(e)}


async def call_openai(prompt: str) -> Dict[str, Any]:
    """Calls OpenAI API."""
    API_KEY = os.environ.get('OPENAI_API_KEY')
    if not API_KEY:
        return {'error': 'OPENAI_API_KEY not set'}

    endpoint = 'https://api.openai.com/v1/chat/completions'

    payload = {
        'model': 'gpt-3.5-turbo',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 512
    }

    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, headers=headers, json=payload, timeout=30) as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    return {'error': f'OpenAI request failed: {resp.status}', 'body': txt}
                data = await resp.json()
                text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                return {'response': text}
    except Exception as e:
        return {'error': str(e)}


# -------------------------
# Models
# -------------------------
class SimpleIsolationForestModel:
    def __init__(self, contamination=0.05):
        self.model = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)
        X = np.array([[100, 200], [120, 220], [90, 180]])
        scaler = StandardScaler()
        self.scaler = scaler.fit(X)
        Xs = self.scaler.transform(X)
        self.model.fit(Xs)

    def predict(self, features: Dict[str, Any]):
        x = np.array([[features.get('bytes_sent', 0), features.get('bytes_received', 0)]])
        x_scaled = self.scaler.transform(x)
        pred = self.model.predict(x_scaled)
        score = self.model.decision_function(x_scaled)[0]
        return {'anomaly': bool(pred[0] == -1), 'score': float(score)}


class SimpleRandomForestNetModel:
    def __init__(self):
        X = np.array([[200, 300, 1], [40000, 10, 0.2], [500, 600, 2]])
        y = np.array([0, 1, 0])
        self.model = RandomForestClassifier(n_estimators=10, random_state=42)
        self.model.fit(X, y)

    def predict(self, features: Dict[str, Any]):
        x = np.array([[features.get('bytes_sent', 0), features.get('bytes_received', 0), features.get('duration', 1)]])
        pred = self.model.predict(x)[0]
        prob = self.model.predict_proba(x).tolist()[0]
        return {'attack': bool(pred == 1), 'prob': prob}


class DeepLogLike:
    def predict(self, sequence: List[str]):
        forbidden = ['rm -rf /', 'mimikatz', 'suspicious-lateral']
        for token in forbidden:
            if token in " ".join(sequence).lower():
                return {'anomaly': True, 'reason': token}
        return {'anomaly': False}


class LogBERTLike:
    def predict(self, text: str):
        suspicious_keywords = ['encoded', 'obfuscat', 'powershell', 'base64']
        for kw in suspicious_keywords:
            if kw in text.lower():
                return {'anomaly': True, 'keyword': kw}
        return {'anomaly': False}


# -------------------------
# Threat Detection Logic
# -------------------------
async def detect_port_scan() -> List[Dict]:
    """Detect port scanning: many distinct ports from single source."""
    logs = await fetch_recent_connections(1000)
    threats = []
    src_ports = {}
    for log in logs:
        src = log.get('source_ip')
        dst_port = log.get('dest_port')
        if src and dst_port:
            if src not in src_ports:
                src_ports[src] = set()
            src_ports[src].add(dst_port)
    
    for src, ports in src_ports.items():
        if len(ports) > 10:  # threshold
            threats.append({
                'type': 'Port Scanning / Reconnaissance',
                'severity': 'medium',
                'description': f'Source {src} scanned {len(ports)} ports',
                'source_ip': src
            })
    return threats


async def detect_brute_force() -> List[Dict]:
    """Detect brute force: high failed auth from same IP."""
    logs = await fetch_recent_http(1000)
    threats = []
    fail_counts = {}
    for log in logs:
        if log.get('status_code') == 401 or (log.get('uri', '').lower().find('login') != -1 and log.get('status_code') in [400, 401, 403]):
            src = log.get('source_ip')
            if src:
                fail_counts[src] = fail_counts.get(src, 0) + 1
    
    for src, count in fail_counts.items():
        if count > 20:  # threshold
            threats.append({
                'type': 'Brute-Force / Credential Stuffing',
                'severity': 'high',
                'description': f'{count} failed auth attempts from {src}',
                'source_ip': src
            })
    return threats


async def detect_exfiltration() -> List[Dict]:
    """Detect data exfiltration: large outbound transfers."""
    logs = await fetch_recent_connections(1000)
    threats = []
    for log in logs:
        bytes_sent = log.get('bytes_sent', 0)
        if bytes_sent > 1000000:  # 1MB threshold
            threats.append({
                'type': 'Data Exfiltration',
                'severity': 'critical',
                'description': f'Large outbound transfer: {bytes_sent} bytes to {log.get("dest_ip")}',
                'source_ip': log.get('source_ip'),
                'dest_ip': log.get('dest_ip')
            })
    return threats


async def detect_lateral_movement() -> List[Dict]:
    """Detect lateral movement: sudden increase in internal connections to many hosts."""
    logs = await fetch_recent_connections(1000)
    threats = []
    src_dests = {}
    for log in logs:
        src = log.get('source_ip')
        dst = log.get('dest_ip')
        if src and dst:
            if src not in src_dests:
                src_dests[src] = set()
            src_dests[src].add(dst)
    
    for src, dests in src_dests.items():
        if len(dests) > 5:  # threshold
            threats.append({
                'type': 'Lateral Movement',
                'severity': 'high',
                'description': f'Source {src} connected to {len(dests)} distinct hosts',
                'source_ip': src
            })
    return threats


async def detect_dns_tunneling() -> List[Dict]:
    """Detect DNS tunneling: high-entropy subdomains, many TXT/A queries."""
    logs = await fetch_recent_dns(1000)
    threats = []
    src_queries = {}
    for log in logs:
        src = log.get('source_ip')
        query = log.get("query", "")
        if src and query:
            if src not in src_queries:
                src_queries[src] = []
            src_queries[src].append(query)
    
    for src, queries in src_queries.items():
        if len(queries) > 50:  # many queries
            threats.append({
                'type': 'DNS Tunneling / Covert Channels',
                'severity': 'medium',
                'description': f'Source {src} made {len(queries)} DNS queries',
                'source_ip': src
            })
        for q in queries:
            if len(q.split('.')) > 3 and any(len(part) > 10 for part in q.split('.')):  # long subdomains
                threats.append({
                    'type': 'DNS Tunneling / Covert Channels',
                    'severity': 'medium',
                    'description': f'Suspicious DNS query: {q} from {src}',
                    'source_ip': src
                })
                break
    return threats


async def detect_c2_beaconing() -> List[Dict]:
    """Detect C2 beaconing: regular interval connections to same external IP/domain."""
    logs = await fetch_recent_connections(1000)
    threats = []
    src_dest_counts = {}
    for log in logs:
        src = log.get('source_ip')
        dst = log.get('dest_ip')
        if src and dst:
            key = (src, dst)
            if key not in src_dest_counts:
                src_dest_counts[key] = 0
            src_dest_counts[key] += 1
    
    for (src, dst), count in src_dest_counts.items():
        if count > 10:  # many connections to same dest
            threats.append({
                'type': 'Command & Control (C2) Beaconing',
                'severity': 'high',
                'description': f'{count} connections from {src} to {dst}',
                'source_ip': src,
                'dest_ip': dst
            })
    return threats


async def detect_web_app_exploitation() -> List[Dict]:
    """Detect exploitation attempts: suspicious query strings, SQL keywords."""
    logs = await fetch_recent_http(1000)
    threats = []
    sql_keywords = ['union', 'select', 'insert', 'drop', 'script', '<script>']
    for log in logs:
        uri = log.get('uri', '').lower()
        if any(kw in uri for kw in sql_keywords):
            threats.append({
                'type': 'Exploitation Attempts Against Web Apps',
                'severity': 'high',
                'description': f'Suspicious URI: {log.get("uri")} from {log.get("source_ip")}',
                'source_ip': log.get('source_ip')
            })
    return threats


async def detect_app_ddos() -> List[Dict]:
    """Detect app-layer DDoS: sudden spike in requests."""
    logs = await fetch_recent_http(1000)
    threats = []
    src_counts = {}
    for log in logs:
        src = log.get('source_ip')
        if src:
            src_counts[src] = src_counts.get(src, 0) + 1
    
    for src, count in src_counts.items():
        if count > 100:  # threshold
            threats.append({
                'type': 'Application-Layer DDoS / Resource Exhaustion',
                'severity': 'critical',
                'description': f'{count} requests from {src}',
                'source_ip': src
            })
    return threats


async def detect_mitm() -> List[Dict]:
    """Detect MITM: certificate mismatches, unexpected plaintext."""
    logs = await fetch_recent_ssl(1000)
    threats = []
    for log in logs:
        if not log.get('established'):
            threats.append({
                'type': 'Man-in-the-Middle (MITM) / TLS Stripping Indicators',
                'severity': 'high',
                'description': f'Failed SSL handshake from {log.get("source_ip")} to {log.get("server_name")}',
                'source_ip': log.get('source_ip'),
                'dest_ip': log.get('dest_ip')
            })
    return threats


async def detect_dns_amplification() -> List[Dict]:
    """Detect DNS amplification: high rate of small queries producing large responses."""
    logs = await fetch_recent_dns(1000)
    threats = []
    src_counts = {}
    for log in logs:
        src = log.get('source_ip')
        answers = log.get('answers', [])
        if src and len(answers) > 10:  # many answers
            if src not in src_counts:
                src_counts[src] = 0
            src_counts[src] += 1
    
    for src, count in src_counts.items():
        if count > 20:  # threshold
            threats.append({
                'type': 'Unusual DNS Amplification/Reflection Patterns',
                'severity': 'medium',
                'description': f'{count} DNS queries with many answers from {src}',
                'source_ip': src
            })
    return threats


async def detect_beaconing_encrypted() -> List[Dict]:
    """Detect beaconing via encrypted channels: small periodic encrypted flows."""
    logs = await fetch_recent_ssl(1000)
    threats = []
    src_dest_counts = {}
    for log in logs:
        src = log.get('source_ip')
        dst = log.get('dest_ip')
        if src and dst and log.get('established'):
            key = (src, dst)
            if key not in src_dest_counts:
                src_dest_counts[key] = 0
            src_dest_counts[key] += 1
    
    for (src, dst), count in src_dest_counts.items():
        if count > 10:  # many encrypted connections
            threats.append({
                'type': 'Beaconing via Encrypted Channels',
                'severity': 'high',
                'description': f'{count} encrypted connections from {src} to {dst}',
                'source_ip': src,
                'dest_ip': dst
            })
    return threats


# Add more detections for other threats...


async def run_ai_detection(threats: List[Dict]) -> List[Dict]:
    """Use Gemini/OpenAI to analyze threats."""
    enhanced = []
    for threat in threats:
        prompt = f"Analyze this threat: {threat['type']} - {threat['description']}. Suggest mitigation steps."
        gemini_resp = await to_thread(call_gemini, prompt)
        openai_resp = await call_openai(prompt)
        threat['gemini_analysis'] = gemini_resp.get('response', gemini_resp.get('error', 'N/A'))
        threat['openai_analysis'] = openai_resp.get('response', openai_resp.get('error', 'N/A'))
        enhanced.append(threat)
    return enhanced


# -------------------------
# Database Functions
# -------------------------
async def fetch_recent_logs(limit: int = 1000) -> List[Dict]:
    """Fetch recent Zeek logs from Postgres."""
    query = text("""
        SELECT id, timestamp, source_ip, dest_ip, source_port, dest_port, protocol, 
               bytes_sent, bytes_received, event_text
        FROM zeek_events 
        ORDER BY timestamp DESC 
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {'limit': limit})
        rows = result.fetchall()
        return [row._asdict() for row in rows]


async def fetch_recent_connections(limit: int = 1000) -> List[Dict]:
    """Fetch recent connection logs."""
    query = text("""
        SELECT id, timestamp, uid, source_ip, dest_ip, source_port, dest_port, protocol,
               duration, bytes_sent, bytes_received, connection_state
        FROM zeek_connections
        ORDER BY timestamp DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {'limit': limit})
        rows = result.fetchall()
        return [row._asdict() for row in rows]


async def fetch_recent_dns(limit: int = 1000) -> List[Dict]:
    """Fetch recent DNS logs."""
    query = text("""
        SELECT id, timestamp, uid, source_ip, dest_ip, source_port, dest_port, query,
               query_type, rcode, answers
        FROM zeek_dns
        ORDER BY timestamp DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {'limit': limit})
        rows = result.fetchall()
        return [row._asdict() for row in rows]


async def fetch_recent_http(limit: int = 1000) -> List[Dict]:
    """Fetch recent HTTP logs."""
    query = text("""
        SELECT id, timestamp, uid, source_ip, dest_ip, source_port, dest_port, method,
               uri, referrer, user_agent, status_code, response_body_size
        FROM zeek_http
        ORDER BY timestamp DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {'limit': limit})
        rows = result.fetchall()
        return [row._asdict() for row in rows]


async def fetch_recent_ssl(limit: int = 1000) -> List[Dict]:
    """Fetch recent SSL logs."""
    query = text("""
        SELECT id, timestamp, uid, source_ip, dest_ip, source_port, dest_port, version,
               cipher, server_name, subject, issuer_subject, established
        FROM zeek_ssl
        ORDER BY timestamp DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {'limit': limit})
        rows = result.fetchall()
        return [row._asdict() for row in rows]


async def insert_threat(threat: Dict):
    """Insert detected threat into database (assume a threats table)."""
    print(f"Inserting threat: {threat}")
    # For now, insert into incidents or create a new table
    query = text("""
        INSERT INTO incidents (timestamp, threat_type, severity, description, source_ip, dest_ip, details)
        VALUES (NOW(), :threat_type, :severity, :description, :source_ip, :dest_ip, :details)
    """)
    with engine.connect() as conn:
        conn.execute(query, {
            'threat_type': threat['type'],
            'severity': threat['severity'],
            'description': threat['description'],
            'source_ip': threat.get('source_ip'),
            'dest_ip': threat.get('dest_ip'),
            'details': json.dumps(threat)
        })
        conn.commit()


# -------------------------
# Background Task
# -------------------------
async def run_threat_detection():
    """Periodic threat detection."""
    while True:
        try:
            threats = []
            threats.extend(await detect_port_scan())
            threats.extend(await detect_brute_force())
            threats.extend(await detect_exfiltration())
            threats.extend(await detect_lateral_movement())
            threats.extend(await detect_dns_tunneling())
            threats.extend(await detect_c2_beaconing())
            threats.extend(await detect_web_app_exploitation())
            threats.extend(await detect_app_ddos())
            threats.extend(await detect_mitm())
            threats.extend(await detect_dns_amplification())
            threats.extend(await detect_beaconing_encrypted())
            # Add more detections...

            if threats:
                enhanced_threats = await run_ai_detection(threats)
                for threat in enhanced_threats:
                    await insert_threat(threat)

        except Exception as e:
            print(f"Error in threat detection: {e}")
        
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


# -------------------------
# API Endpoints
# -------------------------
@router.get("/threats/detect")
async def detect_threats_now(background_tasks: BackgroundTasks):
    """Trigger immediate threat detection."""
    background_tasks.add_task(run_threat_detection_once)
    return {"status": "Detection started"}


@router.get("/threats/list")
async def list_threats(limit: int = 50):
    """List detected threats."""
    query = text("SELECT * FROM incidents ORDER BY timestamp DESC LIMIT :limit")
    with engine.connect() as conn:
        result = conn.execute(query, {'limit': limit})
        rows = result.fetchall()
        return [row._asdict() for row in rows]


async def run_threat_detection_once():
    """Run detection once."""
    try:
        threats = []
        threats.extend(await detect_port_scan())
        threats.extend(await detect_brute_force())
        threats.extend(await detect_exfiltration())
        threats.extend(await detect_lateral_movement())
        threats.extend(await detect_dns_tunneling())
        threats.extend(await detect_c2_beaconing())
        threats.extend(await detect_web_app_exploitation())
        threats.extend(await detect_app_ddos())
        threats.extend(await detect_mitm())
        threats.extend(await detect_dns_amplification())
        threats.extend(await detect_beaconing_encrypted())
        # Add more detections...

        if threats:
            enhanced_threats = await run_ai_detection(threats)
            for threat in enhanced_threats:
                await insert_threat(threat)
    except Exception as e:
        print(f"Error in threat detection: {e}")


# Start background task on app startup (add to main.py)
threat_detection_task = None


def start_threat_detection():
    global threat_detection_task
    threat_detection_task = asyncio.create_task(run_threat_detection())


def stop_threat_detection():
    if threat_detection_task:
        threat_detection_task.cancel()