# port-scan.zeek
# Detects when a single source IP connects to many unique ports quickly.

const port_scan_threshold = 50; # Number of unique ports to trigger alert

event zeek_init()
    {
    print fmt("Port scan detection script loaded. Threshold = %d ports", port_scan_threshold);
    }

global scan_tracker: table[addr] of set[port] = table();

event connection_attempt(c: connection)
    {
    local src = c$id$orig_h;
    local dst_port = c$id$resp_p;

    # Initialize if not tracked
    if ( src !in scan_tracker )
        scan_tracker[src] = set();

    # Add the destination port to the set
    add scan_tracker[src][dst_port];

    # Check if threshold exceeded
    if ( |scan_tracker[src]| > port_scan_threshold )
        {
        print fmt("!!! Port Scan Detected: %s scanned %d unique ports",
                  src, |scan_tracker[src]|);

        }
    }
