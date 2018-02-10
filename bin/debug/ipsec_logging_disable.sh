#!/bin/bash
ndd -set ip ipsec_policy_log_interval 0
ikeadm -n set debug 0x0004
