#!/usr/bin/env python3

import ipaddress
import sys

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <ip_addr>")
    sys.exit(1)

print(str(ipaddress.ip_address(sys.argv[1]).is_private))
