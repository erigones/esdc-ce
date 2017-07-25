#!/usr/bin/env python

from __future__ import print_function
from socket import socket, AF_INET, SOCK_DGRAM
from subprocess import check_output, CalledProcessError
import sys


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


PORT = 5430
BUFFER_SIZE = 1024

try:
    eprint('Determining datacenter name...')
    DC_NAME = check_output(['query_cfgdb', 'get', '/esdc/settings/dc/datacenter_name']).strip()
except (OSError, CalledProcessError) as exc:
    eprint('%s' % exc)
    DC_NAME = '<unknown>'

eprint('Got datacenter name: "%s"' % DC_NAME)
eprint('Running discovery server on port %s' % PORT)

DISCO_MESSAGE = 'cfgdb_discovery'
DISCO_REPLY = 'cfgdb_reply:%s' % DC_NAME

s = socket(AF_INET, SOCK_DGRAM)  # Create UDP socket
s.bind(('', PORT))

while True:
    data, addr = s.recvfrom(BUFFER_SIZE)  # Wait for a packet

    if data.startswith(DISCO_MESSAGE):
        eprint('Got discovery request from %s, sending reply...' % addr[0])
        s.sendto(DISCO_REPLY, addr)
