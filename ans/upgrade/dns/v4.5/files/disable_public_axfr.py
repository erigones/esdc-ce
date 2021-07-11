from pdns.models.pdns_config import PdnsCfg
if not PdnsCfg.objects.filter(key='allow-axfr-ips'):
    # add settings only if it doesn't exist to prevent overwriting custom values
    cf = PdnsCfg(key='allow-axfr-ips', val='')
    cf.save()
