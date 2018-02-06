#!/bin/bash
svcadm disable ike policy
ipseckey flush
svcadm enable ike policy
