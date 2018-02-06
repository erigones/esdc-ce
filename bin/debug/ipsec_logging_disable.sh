#!/bin/sh
ndd -set ip ipsec_policy_log_interval 0
ikeadm set debug 0x0004
