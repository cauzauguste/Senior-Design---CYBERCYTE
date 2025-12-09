"""Threat detection pipeline backed by PostgreSQL.

This module queries the Zeek-derived tables and maps detections to the
SampleThreatList catalog. Each detector returns JSON-safe payloads so the
results can be stored inside the ``incidents`` table and returned via API.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models import (
    Incident,
    ZeekConnection,
    ZeekDNS,
    ZeekEvent,
    ZeekHTTP,
    ZeekSSL,
)


logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_HTTP_TIMEOUT", "30"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
ENABLE_LLM_THREAT_EVAL = _env_bool("ENABLE_LLM_THREAT_EVAL", True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
GEMINI_API_URL = os.getenv(
    "GEMINI_API_URL",
    "https://generativelanguage.googleapis.com/v1beta/models",
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_ORG = os.getenv("OPENAI_ORG")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "ignore")
    if isinstance(value, set):
        normalized = [
            _json_default(item) if isinstance(item, (datetime, list, tuple, set, dict, bytes, bytearray)) else item
            for item in value
        ]
        return sorted(
            normalized,
            key=lambda element: json.dumps(element, sort_keys=True)
            if isinstance(element, dict)
            else str(element),
        )
    if isinstance(value, (list, tuple)):
        return [
            _json_default(item)
            if isinstance(item, (datetime, list, tuple, set, dict, bytes, bytearray))
            else item
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: _json_default(val)
            if isinstance(val, (datetime, list, tuple, set, dict, bytes, bytearray))
            else val
            for key, val in value.items()
        }
    return str(value)


def _json_safe_copy(payload: Any) -> Any:
    try:
        return json.loads(json.dumps(payload, default=_json_default))
    except Exception:  # pragma: no cover - defensive
        logger.debug("Failed to JSON-normalize payload", exc_info=True)
        return payload


def _current_time(now: Optional[datetime] = None) -> datetime:
    return now if now is not None else datetime.utcnow()


def _dns_metrics(domain: str) -> Dict[str, Any]:
    domain = domain or ""
    labels = [label for label in domain.split(".") if label]
    label_count = len(labels)
    max_label_length = max((len(label) for label in labels), default=0)
    if not domain:
        entropy = 0.0
    else:
        counts = Counter(domain)
        total = float(len(domain))
        entropy = -sum((count / total) * math.log2(count / total) for count in counts.values() if count)
    return {
        "entropy": entropy,
        "label_count": label_count,
        "max_label_length": max_label_length,
    }


def _http_post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    body = json.dumps(payload, default=_json_default).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # nosec B310
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset).strip()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        detail = exc.read().decode("utf-8", "ignore") if exc.fp else ""
        logger.warning("HTTP %s when calling %s: %s", exc.code, url, detail)
    except urllib.error.URLError as exc:  # pragma: no cover - network
        logger.warning("Network error calling %s: %s", url, exc.reason)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Unexpected error calling %s", url)
    return None


def _call_gemini_json(prompt: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None

    endpoint = f"{GEMINI_API_URL.rstrip('/')}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": TEMPERATURE,
        },
    }

    raw_response = _http_post_json(endpoint, payload)
    if not raw_response:
        return None

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON payload; returning raw text")
        return raw_response

    candidates = parsed.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        for part in parts:
            text = part.get("text")
            if text:
                return text
        if candidate.get("output"):
            return candidate["output"]
    if parsed.get("error"):
        logger.warning("Gemini error response: %s", parsed["error"])
    return raw_response


def _call_openai_json(prompt: str) -> Optional[str]:
    if not OPENAI_API_KEY:
        return None

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    if OPENAI_ORG:
        headers["OpenAI-Organization"] = OPENAI_ORG

    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
        "response_format": {"type": "json_object"},
    }

    raw_response = _http_post_json(OPENAI_API_URL, payload, headers)
    if not raw_response:
        return None

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        logger.warning("OpenAI returned non-JSON payload; returning raw text")
        return raw_response

    choices = parsed.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        content = message.get("content")
        if content:
            return content
    if parsed.get("error"):
        logger.warning("OpenAI error response: %s", parsed["error"])
    return raw_response


# --- Threat catalog -------------------------------------------------------


THREAT_CATALOG: Sequence[Dict[str, str]] = [
        {
            "id": "T01",
            "name": "Port Scanning / Reconnaissance",
            "description": (
                "Detect sources probing many distinct destination ports or hosts within short windows. "
                "Signals include sequential scans, SYN bursts, and reconnaissance flows. Expected response: "
                "rate-limit or temporarily block the source."
            ),
        },
        {
            "id": "T02",
            "name": "Unauthorized Network Port/Service Changes",
            "description": (
                "Surface newly opened listening services or unexpected service registrations that deviate from "
                "baseline. Highlight rapid changes in service inventory and misconfigurations."
            ),
        },
        {
            "id": "T03",
            "name": "Brute-Force / Credential Stuffing",
            "description": (
                "Identify repeated authentication failures against SSH, RDP, or web apps from single or distributed IPs. "
                "Focus on volume, velocity, and failure ratios to distinguish automated attacks."
            ),
        },
        {
            "id": "T04",
            "name": "Lateral Movement",
            "description": (
                "Detect sudden increases in internal host-to-host communications, SMB/RPC exploration, or unusual "
                "access patterns suggesting pivoting between assets."
            ),
        },
        {
            "id": "T05",
            "name": "Data Exfiltration",
            "description": (
                "Flag large or unusual outbound transfers to external destinations, suspicious protocols, or DNS-based "
                "covert channels. Provide estimated volume and key endpoints involved."
            ),
        },
        {
            "id": "T06",
            "name": "DNS Tunneling / Covert Channels",
            "description": (
                "Look for high-entropy subdomains, frequent TXT/A queries with sizable payloads, or persistent queries "
                "toward a single domain indicative of tunneling."
            ),
        },
        {
            "id": "T07",
            "name": "Command & Control (C2) Beaconing",
            "description": (
                "Highlight regular interval connections to specific external IPs/domains, JA3 anomalies, or repeating "
                "TLS handshakes that signal beaconing behavior."
            ),
        },
        {
            "id": "T08",
            "name": "Web Application Exploitation Attempts",
            "description": (
                "Surface suspicious HTTP requests containing SQLi, RCE, XSS keywords, abnormal response codes, or "
                "payloads targeting known vulnerable paths."
            ),
        },
        {
            "id": "T09",
            "name": "Application-Layer DDoS / Resource Exhaustion",
            "description": (
                "Detect surges in requests per second, abnormal client concentration, or exhausting patterns leading to "
                "latency and 5xx spikes."
            ),
        },
        {
            "id": "T10",
            "name": "Man-in-the-Middle / TLS Stripping Indicators",
            "description": (
                "Identify TLS negotiation anomalies, certificate mismatches, plaintext downgrade attempts, or unexpected "
                "proxies in the communication path."
            ),
        },
        {
            "id": "T11",
            "name": "Supply Chain / Third-Party Service Compromise",
            "description": (
                "Highlight unexpected traffic to new external services, CDN changes, or anomalous behavior directly after "
                "dependency updates or deployments."
            ),
        },
        {
            "id": "T12",
            "name": "Lateral DNS Abuse",
            "description": (
                "Detect conflicting DNS answers, rapid record changes, or resolver inconsistencies that may indicate "
                "poisoning or spoofing inside the environment."
            ),
        },
        {
            "id": "T13",
            "name": "Cloud Metadata Service Abuse",
            "description": (
                "Surfacing unexpected metadata service requests, rapid token fetch attempts, or suspicious use of cloud "
                "instance credentials suggesting compromise."
            ),
        },
        {
            "id": "T14",
            "name": "DNS Amplification / Reflection",
            "description": (
                "Identify asymmetric DNS query/response patterns, sudden spikes in amplification-friendly responses, or "
                "traffic targeting open resolvers."
            ),
        },
        {
            "id": "T15",
            "name": "Compromised API Keys / Token Abuse",
            "description": (
                "Flag unusual API usage volumes, geographic mismatches, or cost spikes that imply abused credentials or "
                "tokens."
            ),
        },
        {
            "id": "T16",
            "name": "Compromised Container / Kubernetes Lateralism",
            "description": (
                "Detect cross-pod or cross-namespace communications outside normal policy, unexpected image pulls, or "
                "abnormal API calls within the cluster."
            ),
        },
        {
            "id": "T17",
            "name": "SSL/TLS Certificate Mis-issuance",
            "description": (
                "Alert on certificates issued by unapproved authorities, sudden certificate changes, or chains that do not "
                "match organizational policy."
            ),
        },
        {
            "id": "T18",
            "name": "Rogue Device / Shadow IT",
            "description": (
                "Identify previously unseen internal devices, unknown MAC/OUI profiles, or anomalous DHCP/DNS behavior "
                "introducing new attack surface."
            ),
        },
        {
            "id": "T19",
            "name": "Beaconing via Encrypted Channels",
            "description": (
                "Detect periodic encrypted sessions with unique JA3 fingerprints, low data volumes, or consistent timing "
                "suggesting hidden beaconing."
            ),
        },
        {
            "id": "T20",
            "name": "Auto-Scaling Abuse / Resource Enumeration",
            "description": (
                "Highlight sudden resource creation bursts, quota exhaustion patterns, or suspicious provisioning activity "
                "that can drive cost or availability impact."
            ),
        },
    ]


CONNECTION_WINDOW_MINUTES = 30
DNS_WINDOW_MINUTES = 30
HTTP_WINDOW_MINUTES = 30
SSL_WINDOW_MINUTES = 60
EVENT_WINDOW_MINUTES = 60
MAX_ITEMS_PER_SECTION = 12
RECENT_SAMPLE_LIMIT = 20


def _collect_connection_context(db: Session, now: datetime) -> Dict[str, Any]:
    since = now - timedelta(minutes=CONNECTION_WINDOW_MINUTES)

    top_port_rows = (
        db.query(
            ZeekConnection.source_ip.label("source_ip"),
            func.count(ZeekConnection.id).label("connection_count"),
            func.count(func.distinct(ZeekConnection.dest_port)).label("distinct_ports"),
            func.count(func.distinct(ZeekConnection.dest_ip)).label("distinct_destinations"),
            func.sum(ZeekConnection.bytes_sent).label("bytes_sent"),
            func.sum(ZeekConnection.bytes_received).label("bytes_received"),
            func.max(ZeekConnection.timestamp).label("last_seen"),
        )
        .filter(
            ZeekConnection.timestamp >= since,
            ZeekConnection.source_ip.isnot(None),
        )
        .group_by(ZeekConnection.source_ip)
        .order_by(desc(func.count(func.distinct(ZeekConnection.dest_port))))
        .limit(MAX_ITEMS_PER_SECTION)
        .all()
    )
    top_port_activity = [
        {
            "source_ip": row.source_ip,
            "connection_count": int(row.connection_count or 0),
            "distinct_ports": int(row.distinct_ports or 0),
            "distinct_destinations": int(row.distinct_destinations or 0),
            "bytes_sent": int(row.bytes_sent or 0),
            "bytes_received": int(row.bytes_received or 0),
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        }
        for row in top_port_rows
    ]

    top_transfer_rows = (
        db.query(
            ZeekConnection.source_ip,
            ZeekConnection.dest_ip,
            func.sum(ZeekConnection.bytes_sent + ZeekConnection.bytes_received).label("total_bytes"),
            func.sum(ZeekConnection.bytes_sent).label("bytes_sent"),
            func.sum(ZeekConnection.bytes_received).label("bytes_received"),
        )
        .filter(
            ZeekConnection.timestamp >= since,
            ZeekConnection.source_ip.isnot(None),
            ZeekConnection.dest_ip.isnot(None),
        )
        .group_by(ZeekConnection.source_ip, ZeekConnection.dest_ip)
        .order_by(desc(func.sum(ZeekConnection.bytes_sent + ZeekConnection.bytes_received)))
        .limit(MAX_ITEMS_PER_SECTION)
        .all()
    )
    top_transfers = [
        {
            "source_ip": row.source_ip,
            "dest_ip": row.dest_ip,
            "total_bytes": int(row.total_bytes or 0),
            "bytes_sent": int(row.bytes_sent or 0),
            "bytes_received": int(row.bytes_received or 0),
        }
        for row in top_transfer_rows
    ]

    connection_state_rows = (
        db.query(
            ZeekConnection.connection_state,
            func.count(ZeekConnection.id),
        )
        .filter(ZeekConnection.timestamp >= since)
        .group_by(ZeekConnection.connection_state)
        .all()
    )
    connection_states = {
        (row[0] or "unknown"): int(row[1] or 0) for row in connection_state_rows
    }

    protocol_rows = (
        db.query(
            ZeekConnection.protocol,
            func.count(ZeekConnection.id),
        )
        .filter(ZeekConnection.timestamp >= since)
        .group_by(ZeekConnection.protocol)
        .all()
    )
    protocol_breakdown = {
        (row[0] or "unknown"): int(row[1] or 0) for row in protocol_rows
    }

    recent_rows = (
        db.query(
            ZeekConnection.timestamp,
            ZeekConnection.source_ip,
            ZeekConnection.dest_ip,
            ZeekConnection.source_port,
            ZeekConnection.dest_port,
            ZeekConnection.protocol,
            ZeekConnection.bytes_sent,
            ZeekConnection.bytes_received,
            ZeekConnection.connection_state,
        )
        .filter(ZeekConnection.timestamp.isnot(None))
        .order_by(ZeekConnection.timestamp.desc())
        .limit(RECENT_SAMPLE_LIMIT)
        .all()
    )
    recent_connections = [
        {
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "source_ip": row.source_ip,
            "dest_ip": row.dest_ip,
            "source_port": row.source_port,
            "dest_port": row.dest_port,
            "protocol": row.protocol,
            "bytes_sent": int(row.bytes_sent or 0),
            "bytes_received": int(row.bytes_received or 0),
            "state": row.connection_state,
        }
        for row in recent_rows
    ]

    return {
        "window_minutes": CONNECTION_WINDOW_MINUTES,
        "top_sources_by_port_diversity": top_port_activity,
        "top_transfers": top_transfers,
        "connection_states": connection_states,
        "protocol_breakdown": protocol_breakdown,
        "recent_samples": recent_connections,
    }


def _collect_dns_context(db: Session, now: datetime) -> Dict[str, Any]:
    since = now - timedelta(minutes=DNS_WINDOW_MINUTES)

    top_query_rows = (
        db.query(
            ZeekDNS.query,
            func.count(ZeekDNS.id).label("query_count"),
            func.count(func.distinct(ZeekDNS.source_ip)).label("unique_sources"),
            func.max(ZeekDNS.timestamp).label("last_seen"),
        )
        .filter(ZeekDNS.timestamp >= since, ZeekDNS.query.isnot(None))
        .group_by(ZeekDNS.query)
        .order_by(desc(func.count(ZeekDNS.id)))
        .limit(MAX_ITEMS_PER_SECTION)
        .all()
    )
    top_queries = []
    for row in top_query_rows:
        metrics = _dns_metrics(row.query or "")
        top_queries.append(
            {
                "query": row.query,
                "query_count": int(row.query_count or 0),
                "unique_sources": int(row.unique_sources or 0),
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
                "entropy": round(metrics["entropy"], 3),
                "label_count": metrics["label_count"],
                "max_label_length": metrics["max_label_length"],
            }
        )

    high_entropy_queries = [entry for entry in top_queries if entry["entropy"] >= 3.5]

    rcode_rows = (
        db.query(ZeekDNS.rcode, func.count(ZeekDNS.id))
        .filter(ZeekDNS.timestamp >= since)
        .group_by(ZeekDNS.rcode)
        .all()
    )
    rcode_breakdown = {
        (row[0] or "NOERROR"): int(row[1] or 0) for row in rcode_rows
    }

    top_source_rows = (
        db.query(
            ZeekDNS.source_ip,
            func.count(ZeekDNS.id).label("query_count"),
            func.count(func.distinct(ZeekDNS.query)).label("distinct_queries"),
        )
        .filter(ZeekDNS.timestamp >= since, ZeekDNS.source_ip.isnot(None))
        .group_by(ZeekDNS.source_ip)
        .order_by(desc(func.count(ZeekDNS.id)))
        .limit(MAX_ITEMS_PER_SECTION)
        .all()
    )
    top_sources = [
        {
            "source_ip": row.source_ip,
            "query_count": int(row.query_count or 0),
            "distinct_queries": int(row.distinct_queries or 0),
        }
        for row in top_source_rows
    ]

    recent_rows = (
        db.query(
            ZeekDNS.timestamp,
            ZeekDNS.source_ip,
            ZeekDNS.dest_ip,
            ZeekDNS.query,
            ZeekDNS.answers,
            ZeekDNS.rcode,
        )
        .filter(ZeekDNS.timestamp.isnot(None))
        .order_by(ZeekDNS.timestamp.desc())
        .limit(RECENT_SAMPLE_LIMIT)
        .all()
    )
    recent_samples = [
        {
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "source_ip": row.source_ip,
            "dest_ip": row.dest_ip,
            "query": row.query,
            "answers": row.answers,
            "rcode": row.rcode,
        }
        for row in recent_rows
    ]

    return {
        "window_minutes": DNS_WINDOW_MINUTES,
        "top_queries": top_queries,
        "high_entropy_queries": high_entropy_queries,
        "rcode_breakdown": rcode_breakdown,
        "top_sources": top_sources,
        "recent_samples": recent_samples,
    }


def _collect_http_context(db: Session, now: datetime) -> Dict[str, Any]:
    since = now - timedelta(minutes=HTTP_WINDOW_MINUTES)

    top_uri_rows = (
        db.query(
            ZeekHTTP.uri,
            func.count(ZeekHTTP.id).label("request_count"),
            func.count(func.distinct(ZeekHTTP.source_ip)).label("unique_sources"),
        )
        .filter(ZeekHTTP.timestamp >= since, ZeekHTTP.uri.isnot(None))
        .group_by(ZeekHTTP.uri)
        .order_by(desc(func.count(ZeekHTTP.id)))
        .limit(MAX_ITEMS_PER_SECTION)
        .all()
    )
    top_uris = [
        {
            "uri": row.uri,
            "request_count": int(row.request_count or 0),
            "unique_sources": int(row.unique_sources or 0),
        }
        for row in top_uri_rows
    ]

    status_rows = (
        db.query(ZeekHTTP.status_code, func.count(ZeekHTTP.id))
        .filter(ZeekHTTP.timestamp >= since)
        .group_by(ZeekHTTP.status_code)
        .all()
    )
    status_breakdown = {str(row[0]): int(row[1] or 0) for row in status_rows}

    method_rows = (
        db.query(ZeekHTTP.method, func.count(ZeekHTTP.id))
        .filter(ZeekHTTP.timestamp >= since)
        .group_by(ZeekHTTP.method)
        .all()
    )
    method_breakdown = {
        (row[0] or "UNKNOWN"): int(row[1] or 0) for row in method_rows
    }

    ua_rows = (
        db.query(ZeekHTTP.user_agent, func.count(ZeekHTTP.id))
        .filter(ZeekHTTP.timestamp >= since, ZeekHTTP.user_agent.isnot(None))
        .group_by(ZeekHTTP.user_agent)
        .order_by(desc(func.count(ZeekHTTP.id)))
        .limit(MAX_ITEMS_PER_SECTION)
        .all()
    )
    top_user_agents = [
        {
            "user_agent": row[0],
            "request_count": int(row[1] or 0),
        }
        for row in ua_rows
    ]

    recent_rows = (
        db.query(
            ZeekHTTP.timestamp,
            ZeekHTTP.source_ip,
            ZeekHTTP.dest_ip,
            ZeekHTTP.method,
            ZeekHTTP.uri,
            ZeekHTTP.status_code,
        )
        .filter(ZeekHTTP.timestamp.isnot(None))
        .order_by(ZeekHTTP.timestamp.desc())
        .limit(RECENT_SAMPLE_LIMIT)
        .all()
    )
    recent_samples = [
        {
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "source_ip": row.source_ip,
            "dest_ip": row.dest_ip,
            "method": row.method,
            "uri": row.uri,
            "status_code": row.status_code,
        }
        for row in recent_rows
    ]

    return {
        "window_minutes": HTTP_WINDOW_MINUTES,
        "top_uris": top_uris,
        "status_breakdown": status_breakdown,
        "method_breakdown": method_breakdown,
        "top_user_agents": top_user_agents,
        "recent_samples": recent_samples,
    }


def _collect_ssl_context(db: Session, now: datetime) -> Dict[str, Any]:
    since = now - timedelta(minutes=SSL_WINDOW_MINUTES)

    top_sni_rows = (
        db.query(
            ZeekSSL.server_name,
            func.count(ZeekSSL.id).label("session_count"),
            func.count(func.distinct(ZeekSSL.source_ip)).label("unique_sources"),
        )
        .filter(ZeekSSL.timestamp >= since, ZeekSSL.server_name.isnot(None))
        .group_by(ZeekSSL.server_name)
        .order_by(desc(func.count(ZeekSSL.id)))
        .limit(MAX_ITEMS_PER_SECTION)
        .all()
    )
    top_server_names = [
        {
            "server_name": row.server_name,
            "session_count": int(row.session_count or 0),
            "unique_sources": int(row.unique_sources or 0),
        }
        for row in top_sni_rows
    ]

    version_rows = (
        db.query(ZeekSSL.version, func.count(ZeekSSL.id))
        .filter(ZeekSSL.timestamp >= since)
        .group_by(ZeekSSL.version)
        .all()
    )
    protocol_versions = {
        (row[0] or "unknown"): int(row[1] or 0) for row in version_rows
    }

    failed_rows = (
        db.query(
            ZeekSSL.timestamp,
            ZeekSSL.source_ip,
            ZeekSSL.dest_ip,
            ZeekSSL.server_name,
            ZeekSSL.issuer,
            ZeekSSL.subject,
            ZeekSSL.version,
        )
        .filter(ZeekSSL.timestamp >= since, ZeekSSL.established == False)  # noqa: E712
        .order_by(ZeekSSL.timestamp.desc())
        .limit(MAX_ITEMS_PER_SECTION)
        .all()
    )
    failed_handshakes = [
        {
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "source_ip": row.source_ip,
            "dest_ip": row.dest_ip,
            "server_name": row.server_name,
            "issuer": row.issuer,
            "subject": row.subject,
            "version": row.version,
        }
        for row in failed_rows
    ]

    recent_rows = (
        db.query(
            ZeekSSL.timestamp,
            ZeekSSL.source_ip,
            ZeekSSL.dest_ip,
            ZeekSSL.server_name,
            ZeekSSL.issuer,
            ZeekSSL.subject,
            ZeekSSL.version,
            ZeekSSL.established,
        )
        .filter(ZeekSSL.timestamp.isnot(None))
        .order_by(ZeekSSL.timestamp.desc())
        .limit(RECENT_SAMPLE_LIMIT)
        .all()
    )
    recent_samples = [
        {
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "source_ip": row.source_ip,
            "dest_ip": row.dest_ip,
            "server_name": row.server_name,
            "issuer": row.issuer,
            "subject": row.subject,
            "version": row.version,
            "established": bool(row.established),
        }
        for row in recent_rows
    ]

    return {
        "window_minutes": SSL_WINDOW_MINUTES,
        "top_server_names": top_server_names,
        "protocol_versions": protocol_versions,
        "failed_handshakes": failed_handshakes,
        "recent_samples": recent_samples,
    }


def _collect_event_context(db: Session, now: datetime) -> Dict[str, Any]:
    since = now - timedelta(minutes=EVENT_WINDOW_MINUTES)

    type_rows = (
        db.query(
            ZeekEvent.log_type,
            func.count(ZeekEvent.id),
        )
        .filter(ZeekEvent.timestamp >= since)
        .group_by(ZeekEvent.log_type)
        .all()
    )
    counts_by_type = {
        (row[0] or "unknown"): int(row[1] or 0) for row in type_rows
    }

    severity_rows = (
        db.query(
            ZeekEvent.severity,
            func.count(ZeekEvent.id),
        )
        .filter(ZeekEvent.timestamp >= since)
        .group_by(ZeekEvent.severity)
        .all()
    )
    counts_by_severity = {
        (row[0] or "info"): int(row[1] or 0) for row in severity_rows
    }

    recent_rows = (
        db.query(
            ZeekEvent.timestamp,
            ZeekEvent.log_type,
            ZeekEvent.source_ip,
            ZeekEvent.dest_ip,
            ZeekEvent.severity,
            ZeekEvent.event_text,
        )
        .filter(ZeekEvent.timestamp.isnot(None))
        .order_by(ZeekEvent.timestamp.desc())
        .limit(RECENT_SAMPLE_LIMIT)
        .all()
    )
    recent_events = [
        {
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "log_type": row.log_type,
            "source_ip": row.source_ip,
            "dest_ip": row.dest_ip,
            "severity": row.severity,
            "event_text": row.event_text,
        }
        for row in recent_rows
    ]

    return {
        "window_minutes": EVENT_WINDOW_MINUTES,
        "counts_by_type": counts_by_type,
        "counts_by_severity": counts_by_severity,
        "recent_events": recent_events,
    }


def collect_detection_context(db: Session, now: datetime) -> Dict[str, Any]:
    return {
        "generated_at": now.isoformat(),
        "connection_window_minutes": CONNECTION_WINDOW_MINUTES,
        "dns_window_minutes": DNS_WINDOW_MINUTES,
        "http_window_minutes": HTTP_WINDOW_MINUTES,
        "ssl_window_minutes": SSL_WINDOW_MINUTES,
        "event_window_minutes": EVENT_WINDOW_MINUTES,
        "connections": _collect_connection_context(db, now),
        "dns": _collect_dns_context(db, now),
        "http": _collect_http_context(db, now),
        "ssl": _collect_ssl_context(db, now),
        "events": _collect_event_context(db, now),
    }


DETECTED_STATUSES = {"detected", "likely_detected", "confirmed", "probable"}


class LLMEvaluator:
    def __init__(self) -> None:
        if not ENABLE_LLM_THREAT_EVAL:
            raise RuntimeError("ENABLE_LLM_THREAT_EVAL must be true when using LLM-driven detection.")
        if not (GEMINI_API_KEY or OPENAI_API_KEY):
            raise RuntimeError("Gemini/OpenAI API credentials are required for threat detection")
        self._last_model: Optional[str] = None

        def assess_threats(
            self,
            threat_catalog: Sequence[Dict[str, str]],
            context: Dict[str, Any],
            timestamp: datetime,
        ) -> List[Dict[str, Any]]:
            catalog_lookup = {item["id"].upper(): item for item in threat_catalog}
            prompt = self._build_prompt(threat_catalog, context, timestamp)
            raw_text = self._invoke_models(prompt)
            detections_data = self._parse_llm_json(raw_text)
            if not detections_data:
                raise RuntimeError("LLM threat evaluation returned no detections")

            context_hash = hashlib.sha256(
                json.dumps(context, default=_json_default, sort_keys=True).encode("utf-8")
            ).hexdigest()
            context_summary = {
                "generated_at": context.get("generated_at"),
                "connection_window_minutes": context.get("connection_window_minutes"),
                "dns_window_minutes": context.get("dns_window_minutes"),
                "http_window_minutes": context.get("http_window_minutes"),
                "ssl_window_minutes": context.get("ssl_window_minutes"),
                "event_window_minutes": context.get("event_window_minutes"),
            }

            results: List[Dict[str, Any]] = []
            for item in detections_data:
                normalized = self._normalize_detection(
                    item,
                    catalog_lookup,
                    context_summary,
                    context_hash,
                    raw_text,
                )
                results.append(normalized)
            return results

        def _build_prompt(
            self,
            threat_catalog: Sequence[Dict[str, str]],
            context: Dict[str, Any],
            timestamp: datetime,
        ) -> str:
            threat_json = json.dumps(threat_catalog, indent=2)
            context_json = json.dumps(context, default=_json_default, indent=2)
            return (
                "You are a senior SOC analyst. Review the telemetry summary and evaluate each threat in the catalog.\n"
                "Return JSON matching this schema (no extra text):\n"
                "{\n"
                "  \"detections\": [\n"
                "    {\n"
                "      \"threat_id\": \"T01\",\n"
                "      \"status\": \"detected|likely_detected|not_detected|inconclusive\",\n"
                "      \"severity\": \"critical|high|medium|low|informational\",\n"
                "      \"confidence\": 0.0-1.0,\n"
                "      \"source_ips\": [\"...\"],\n"
                "      \"dest_ips\": [\"...\"],\n"
                "      \"summary\": \"short assessment\",\n"
                "      \"recommended_actions\": [\"...\"]\n"
                "    }\n"
                "  ]\n"
                "}\n"
                "Always include one entry per threat in the catalog.\n"
                f"Threat catalog (reference):\n{threat_json}\n\n"
                f"Telemetry summary generated at {timestamp.isoformat()}:\n{context_json}\n"
            )

        def _invoke_models(self, prompt: str) -> str:
            if GEMINI_API_KEY:
                response = _call_gemini_json(prompt)
                if response:
                    self._last_model = f"gemini:{GEMINI_MODEL}"
                    return response
            if OPENAI_API_KEY:
                response = _call_openai_json(prompt)
                if response:
                    self._last_model = f"openai:{OPENAI_MODEL}"
                    return response
            raise RuntimeError("No LLM response received from Gemini or OpenAI")

        @staticmethod
        def _parse_llm_json(text: Optional[str]) -> Optional[List[Dict[str, Any]]]:
            if not text:
                return None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        parsed = json.loads(text[start : end + 1])
                    except Exception:
                        return None
                else:
                    return None

            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            if isinstance(parsed, dict):
                for key in ("detections", "results", "threats"):
                    value = parsed.get(key)
                    if isinstance(value, list):
                        return [item for item in value if isinstance(item, dict)]
                return [parsed]
            return None

        @staticmethod
        def _ensure_list(value: Any) -> List[str]:
            if value is None:
                return []
            if isinstance(value, (list, tuple, set)):
                return [str(item) for item in value if item]
            if isinstance(value, str):
                return [value] if value else []
            return [str(value)]

        @staticmethod
        def _normalize_confidence(value: Any, default: float = 0.5) -> float:
            if value is None:
                return default
            try:
                confidence = float(value)
            except (TypeError, ValueError):
                return default
            return max(0.0, min(confidence, 1.0))

        def _normalize_detection(
            self,
            item: Dict[str, Any],
            catalog_lookup: Dict[str, Dict[str, str]],
            context_summary: Dict[str, Any],
            context_hash: str,
            raw_text: str,
        ) -> Dict[str, Any]:
            threat_id = (item.get("threat_id") or item.get("id") or "").strip().upper()
            threat_name = item.get("threat") or item.get("name")
            if not threat_id and threat_name:
                for key, entry in catalog_lookup.items():
                    if entry["name"].lower() == threat_name.lower():
                        threat_id = key
                        break
            catalog_entry = catalog_lookup.get(threat_id) if threat_id else None
            if catalog_entry and not threat_name:
                threat_name = catalog_entry["name"]
            if not threat_id:
                threat_id = "UNKNOWN"
            if not threat_name:
                threat_name = catalog_entry["name"] if catalog_entry else "Unknown Threat"

            status = (item.get("status") or "inconclusive").strip().lower()
            if status not in {"detected", "likely_detected", "probable", "confirmed", "not_detected", "inconclusive"}:
                status = "inconclusive"

            severity = (item.get("severity") or "medium").strip().lower()
            if severity not in {"critical", "high", "medium", "low", "informational"}:
                severity = "medium"

            confidence = self._normalize_confidence(item.get("confidence"))
            source_ips = self._ensure_list(
                item.get("source_ips")
                or item.get("sources")
                or item.get("source_ip")
            )
            dest_ips = self._ensure_list(
                item.get("dest_ips")
                or item.get("destinations")
                or item.get("dest_ip")
            )
            summary = item.get("summary") or item.get("explanation")
            if not summary and catalog_entry:
                summary = catalog_entry.get("description")
            recommended_actions = self._ensure_list(
                item.get("recommended_actions")
                or item.get("recommendations")
                or item.get("actions")
            )

            details = {
                "summary": summary,
                "recommended_actions": recommended_actions,
                "source_ips": source_ips,
                "dest_ips": dest_ips,
                "llm_result": item,
                "llm_model": self._last_model,
                "llm_raw_response": raw_text,
                "context_summary": context_summary,
                "context_snapshot_hash": context_hash,
            }

            return {
                "threat_id": threat_id,
                "threat": threat_name,
                "status": status,
                "severity": severity,
                "confidence": confidence,
                "source_ip": source_ips[0] if source_ips else None,
                "dest_ip": dest_ips[0] if dest_ips else None,
                "details": details,
            }


def run_all_detections(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        execution_time = _current_time(now)
        db = SessionLocal()
        evaluator = LLMEvaluator()
        results: List[Dict[str, Any]] = []

        try:
            context = collect_detection_context(db, execution_time)
            try:
                detections = evaluator.assess_threats(THREAT_CATALOG, context, execution_time)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("LLM threat evaluation failed")
                db.rollback()
                error_payload = {
                    "threat_id": "LLM",
                    "threat": "LLM Threat Evaluation",
                    "severity": "low",
                    "status": "error",
                    "timestamp": execution_time,
                    "error": str(exc),
                }
                results.append(_json_safe_copy(error_payload))
                return results

            for detection in detections:
                detection.setdefault("timestamp", execution_time)
                payload = _json_safe_copy(detection)
                results.append(payload)

                status = payload.get("status", "").lower()
                if status not in DETECTED_STATUSES:
                    continue

                incident = Incident(
                    threat_type=payload.get("threat"),
                    severity=payload.get("severity", "medium"),
                    source_ip=payload.get("source_ip"),
                    dest_ip=payload.get("dest_ip"),
                    details=payload.get("details"),
                    timestamp=execution_time,
                )
                db.add(incident)

            db.commit()
            return results
        finally:
            db.close()

