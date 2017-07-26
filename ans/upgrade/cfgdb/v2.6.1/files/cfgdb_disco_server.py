#!/usr/bin/env python

from __future__ import print_function
from socket import socket, AF_INET, SOCK_DGRAM
from subprocess import check_output, CalledProcessError
import sys


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def get_dc_name():
    try:
        eprint('Determining datacenter name...')
        dc_name = check_output(['query_cfgdb', 'get', '/esdc/settings/dc/datacenter_name']).strip()
    except (OSError, CalledProcessError) as exc:
        eprint('%s' % exc)
        dc_name = '<unknown>'

    eprint('Got datacenter name: "%s"' % dc_name)
    return dc_name


PORT = 5430
BUFFER_SIZE = 1024
DISCO_MESSAGE = 'cfgdb_discovery'
DISCO_REPLY = None

eprint('Running discovery server on port %s' % PORT)
s = socket(AF_INET, SOCK_DGRAM)  # Create UDP socket
s.bind(('', PORT))

while True:
    data, addr = s.recvfrom(BUFFER_SIZE)  # Wait for a packet

    if data.startswith(DISCO_MESSAGE):
        if DISCO_REPLY is None:
            DISCO_REPLY = 'cfgdb_reply:%s' % get_dc_name()

        eprint('Got discovery request from %s, sending reply...' % addr[0])
        s.sendto(DISCO_REPLY, addr)
