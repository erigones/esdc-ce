"""
PowerDNS
http://wiki.powerdns.com/trac/wiki/fields
http://doc.powerdns.com/html/generic-mypgsql-backends.html
"""
from django.db.models.signals import post_delete, post_save

from pdns.models.record import Record
from pdns.models.record import Domain

post_save.connect(Record.post_save_record, sender=Record, dispatch_uid='post_save_record')
post_delete.connect(Record.post_delete_record, sender=Record, dispatch_uid='post_delete_record')
