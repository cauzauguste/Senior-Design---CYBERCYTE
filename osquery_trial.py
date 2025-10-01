import subprocess
import json
from datetime import datetime

THRESHOLD = 50

def run_osquery(query):
    """Run an osquery query and return JSON results."""
    cmd = ["osqueryi", "--json", query]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Osquery error: {result.stderr.strip()}")
    return json.loads(result.stdout)

def detect_port_scans():
  
    query = """SELECT
        p.pid,
        p.name,
        p.cmdline,
        COUNT(n.remote_port) AS distinct_ports
    FROM
        processes AS p
    JOIN
        process_open_sockets AS n
    ON
        p.pid = n.pid
    GROUP BY
        p.pid
    HAVING
        distinct_ports > {threshold};""".format(threshold=THRESHOLD)
    
    result = run_osquery(query)

    if result:
        print(f"[{datetime.utcnow()}] Port scan activity detected:")
        for row in result:
            print(f"  PID: {row['pid']} | Process: {row['name']} | Ports Hit: {row['distinct_ports']}")
    else:
        print(f"[{datetime.utcnow()}] No port scanning detected.")

if __name__ == "__main__":
    detect_port_scans()
