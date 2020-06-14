#!/usr/bin/env python

# To sort template json case-insensitive according to item names, do (example for template t_svc-dns):
# cat t_svc-dns.json | jq --indent 4 '.zabbix_export.templates[].items |= sort_by(.name | ascii_upcase)' > t_svc-dns.json.sorted

from vms.models import DefaultDc
from api.mon.backends.zabbix.internal import InternalZabbix
import json
import sys

if len(sys.argv) < 2 or not len(sys.argv[1]):
	print("Please specify template name. Nothing to do.")
	sys.exit(21)

tmpl_name = sys.argv[1]
dc = DefaultDc()
zx = InternalZabbix(dc)

tmpl_id = zx.zapi.template.get({"output": ["templateid"],"filter": {"host": [tmpl_name]}})

if not len(tmpl_id):
	print("Template '%s' was not found" % tmpl_name)
	sys.exit(22)

tmpl_id = int(tmpl_id[0]['templateid'])

tmpl = zx.zapi.configuration.export({"output": "extend", "sortfield": "host", "format": "json", "options": {"templates": [tmpl_id]}})

tmpl_text = json.dumps(json.loads(tmpl), indent=4, separators=(',', ': '))

print(tmpl_text)
