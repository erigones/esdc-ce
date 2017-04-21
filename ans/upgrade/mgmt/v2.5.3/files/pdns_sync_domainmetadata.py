from django.db import connections
from pdns.models import Domain


query = "INSERT INTO domainmetadata (domain_id, kind, content) VALUES (%s, 'ALLOW-AXFR-FROM', 'AUTO-NS')"

with connections["pdns"].cursor() as cursor:
    cursor.execute('SELECT DISTINCT domain_id FROM domainmetadata');
    ok_domains = [row[0] for row in cursor.fetchall()]
    affected_domains = Domain.objects.exclude(id__in=ok_domains).values_list('id', flat=True);

    for domain_id in affected_domains:
        cursor.execute(query, [domain_id])
        print('Inserted domainmetadata for domain ID: %s' % domain_id)
