#!/usr/bin/env python

from __future__ import print_function
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST, timeout
import sys


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


PORT = 5430
BUFFER_SIZE = 1024
DISCO_TIMEOUT = 2
DISCO_MESSAGE = 'cfgdb_discovery'
DISCO_REPLY = 'cfgdb_reply'

eprint('Discovering cfgdb server...')
s = socket(AF_INET, SOCK_DGRAM)  # Create UDP socket
s.bind(('', 0))
s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)  # This is a broadcast socket
s.settimeout(DISCO_TIMEOUT)
s.sendto(DISCO_MESSAGE, ('<broadcast>', PORT))

try:
    data, addr = s.recvfrom(BUFFER_SIZE)  # Wait for a packet

    if data.startswith(DISCO_REPLY):
        dc_name = data.split(':')[-1].strip()
        eprint('Got discovery reply from "%s" with datacenter name: "%s"' % (addr[0], dc_name))
        print(addr[0])
        sys.exit(0)
    else:
        eprint('Got unknown message from "%s": %s' % (addr[0], data))
        sys.exit(2)
except timeout:
    eprint('cfgdb server not found')
    sys.exit(1)
