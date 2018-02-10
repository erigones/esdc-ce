#!/bin/bash
svcadm disable ike policy
ipseckey -n flush
svcadm enable ike policy
