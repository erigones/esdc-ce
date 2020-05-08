"""
PowerDNS
http://wiki.powerdns.com/trac/wiki/fields
http://doc.powerdns.com/html/generic-mypgsql-backends.html
"""
from django.db.models.signals import post_delete, post_save

from pdns.models.record import Record
from pdns.models.record import Domain
from pdns.models.pdns_config import PdnsCfg
from pdns.models.pdns_config import PdnsRecursorCfg
from pdns.models.pdns_config import RecurseNetworks

post_save.connect(Domain.post_save_domain, sender=Domain, dispatch_uid='post_save_domain')
post_save.connect(Record.post_save_record, sender=Record, dispatch_uid='post_save_record')
post_delete.connect(Record.post_delete_record, sender=Record, dispatch_uid='post_delete_record')

post_save.connect(PdnsCfg.post_save_entry, sender=PdnsCfg, dispatch_uid='post_save_entry')
post_delete.connect(PdnsCfg.post_delete_entry, sender=PdnsCfg, dispatch_uid='post_delete_entry')

post_save.connect(PdnsRecursorCfg.post_save_entry, sender=PdnsRecursorCfg, dispatch_uid='post_save_entry')
post_delete.connect(PdnsRecursorCfg.post_delete_entry, sender=PdnsRecursorCfg, dispatch_uid='post_delete_entry')

post_save.connect(RecurseNetworks.post_save_entry, sender=RecurseNetworks, dispatch_uid='post_save_entry')
post_delete.connect(RecurseNetworks.post_delete_entry, sender=RecurseNetworks, dispatch_uid='post_delete_entry')
