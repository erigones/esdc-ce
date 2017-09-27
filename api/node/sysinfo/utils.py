import re
import json

from django.utils.datastructures import OrderedDict
from django.utils.six import PY3


if PY3:
    t_long = int
else:
    t_long = long


def __get_indentation(line):
    i = 0
    for c in line:
        if c == ' ':
            i += 1
        else:
            return i
    return i


def _parse_zpool_status(zpool_status):
    x = zpool_status.strip().splitlines()
    pool = x[0].replace('pool: ', '').strip()
    data = OrderedDict()
    go = False
    group = pool
    subgroup = ''

    for line in x:
        if go:
            if not (line and line.startswith('\t')):
                break

            indent = __get_indentation(line.replace('\t', '', 1))
            item = line.split()[0]

            if indent:
                if item in ('replacing', 'spare'):
                    continue
                elif re.match(r'^c[0-9]', item):
                    if subgroup not in data[group]:
                        data[group][subgroup] = []

                    data[group][subgroup].append(item)
                else:
                    subgroup = item
            else:
                group = item
                subgroup = ''
                data[group] = OrderedDict()

        elif line.strip().split() == ['NAME', 'STATE', 'READ', 'WRITE', 'CKSUM']:
            go = True

    return pool, data


def _parse_imgadm_sources(imgadm_sources):
    """imgadm sources -j output can produce different output depending on SmartOS version (list of strings or dicts)"""
    if not imgadm_sources:
        return []

    if isinstance(imgadm_sources[-1], dict):
        return [src['url'] for src in imgadm_sources]
    else:
        return imgadm_sources


def parse_esysinfo(stdout):
    """Return dict of parsed esysinfo elements {sysinfo, diskinfo, zpools, config}"""
    x = stdout.split('||||')
    num_items = len(x)
    sysinfo = json.loads(x[0])
    img_sources = _parse_imgadm_sources(json.loads(x[1]))
    diskinfo = {}
    zpools = {}
    config = x[6].strip()
    sshkey = x[7].strip()
    nictags = []

    # noinspection PyBroadException
    try:
        img_initial = json.loads(x[8].strip())
    except:
        img_initial = None

    for i in x[2].strip().splitlines():
        disk = i.split()
        diskinfo[disk[1]] = {'type': disk[0], 'VID': disk[2], 'PID': ' '.join(disk[3:-3]),
                             'size': int(t_long(disk[-3]) / 1048576), 'RMV': disk[-2], 'SSD': disk[-1]}

    for i in x[3].strip().splitlines():
        pool, size = map(str.strip, str(i).split())
        zpools[pool] = {'size': int(t_long(size) / 1048576)}

    for i in x[4].strip().splitlines():
        pool, used, avail = map(str.strip, str(i).split())
        zpools[pool]['size'] = int((t_long(used) + t_long(avail)) / 1048576)

    for i in re.split(r'\s*pool: ', x[5].strip()):
        i = i.strip()
        if i:
            pool, data = _parse_zpool_status(i)
            zpools[pool]['config'] = data

    if num_items >= 10:
        for i in x[9].strip().splitlines():
            name, mac, link, typ = map(lambda c: None if c == '-' else c, map(str.strip, str(i).split('|')))
            nictags.append({'name': name, 'mac': mac, 'link': link, 'type': typ})

    return {
        'sysinfo': sysinfo,
        'diskinfo': diskinfo,
        'zpools': zpools,
        'config': config,
        'sshkey': sshkey,
        'img_sources': img_sources,
        'img_initial': img_initial,
        'nictags': nictags,
    }
