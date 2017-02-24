from django.utils.translation import ugettext_noop as _

from vms.models import Vm


def _zone_fs_items(graph_options, item_id):
    """Return zabbix search params"""
    items_search = graph_options['items_search'].copy()
    items_search['sortorder'] = item_id  # 0 - ASC, 1 - DESC

    return items_search


def _threshold_to_grid(val):
    """Return graph threshold configuration"""
    return {
        'markings': [
            {'color': '#FF0000', 'lineWidth': 1, 'yaxis': {'from': val, 'to': val}},
        ]
    }


def _cpu_usage_cap(graph_options, vm):
    """Add CPU usage threshold"""
    cap = vm.vcpus_active

    if cap:
        graph_options['options'] = graph_options['options'].copy()
        graph_options['options']['grid'] = _threshold_to_grid(cap * 100)

    return graph_options


def _mem_usage_cap(graph_options, vm):
    """Add RAM usage threshold"""
    cap = vm.ram_active

    if cap:
        graph_options['options'] = graph_options['options'].copy()
        graph_options['options']['grid'] = _threshold_to_grid(cap * 1048576)

    return graph_options


class _GraphItems(dict):
    """
    Graph Item Dictionary.
    """
    def get_options(self, item, *args, **kwargs):
        opts = self[item]
        fun = opts.pop('_opts_fun', None)

        if fun:
            opts = fun(opts, *args, **kwargs)

        return opts


GRAPH_UPDATE_INTERVAL = 30
GRAPH_STACK_SERIES = {
    'stack': True,
    'lines': {
        'fillColor': {'colors': [{'opacity': 0.6}]},
        'lineWidth': 0.2,
    }
}
GRAPH_LINE_SERIES = {
    'lines': {
        'lineWidth': 2.0,
        'fill': False,
    },
}
GRAPH_ITEMS = _GraphItems({
    'cpu-usage': {
        'desc': _('Total compute node CPU consumed by the VM.'),
        'items': ('vm.cpu.sys', 'vm.cpu.user'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
        '_opts_fun': _cpu_usage_cap,
    },

    'cpu-waittime': {
        'desc': _('Total amount of time spent in CPU run queue by the VM.'),
        'items': ('vm.cpu.wait',),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': 'second', 'min': 0},
        },
    },

    'cpu-load': {
        'desc': _('1-minute load average.'),
        'items': ('kstat.get[zones:{$ZONEID}::avenrun_1min]',),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'mem-usage': {
        'desc': _('Total compute node physical memory consumed by the VM.'),
        'items': ('kstat.get[memory_cap:{$ZONEID}::rss]',),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byte', 'min': 0},
        },
        '_opts_fun': _mem_usage_cap,
    },

    'swap-usage': {
        'desc': _('Total compute node swap space used by the VM.'),
        'items': ('kstat.get[memory_cap:{$ZONEID}::swap]',),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byte', 'min': 0},
        },
    },

    'net-bandwidth': {
        'desc': _('The amount of received and sent network traffic through the virtual network interface.'),
        'items': ('vm.net[net%(id)d,rbytes64]', 'vm.net[net%(id)d,obytes64]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'bitRate', 'min': 0},
        },
    },

    'net-packets': {
        'desc': _('The amount of received and sent packets through the virtual network interface.'),
        'items': ('vm.net[net%(id)d,ipackets64]', 'vm.net[net%(id)d,opackets64]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'disk-throughput': {
        'desc': _('The amount of written and read data on the virtual hard drive.'),
        'required_ostype': Vm.KVM,
        'items': ('vm.disk.io[disk%(id)d,read]', 'vm.disk.io[disk%(id)d,written]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'disk-io': {
        'desc': _('The amount of write and read I/O operations performed on the virtual hard drive.'),
        'required_ostype': Vm.KVM,
        'items': ('vm.disk.io[disk%(id)d,reads]', 'vm.disk.io[disk%(id)d,writes]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'fs-throughput': {
        'desc': _('The amount of written and read data on the virtual hard drive.'),
        'required_ostype': Vm.ZONE,
        'items': ('kstat.get[unix:0:vopstats_disk%(id)d:read_bytes]',
                  'kstat.get[unix:0:vopstats_disk%(id)d:write_bytes]'),
        'items_search': {'search': {'key_': 'kstat.get[unix:0:vopstats_*_bytes*'}, 'searchWildcardsEnabled': True,
                         'limit': 2, 'sortfield': ['name'], 'sortorder': '???'},
        'items_search_fun': _zone_fs_items,
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'fs-io': {
        'desc': _('The amount of write and read I/O operations performed on the virtual hard drive.'),
        'required_ostype': Vm.ZONE,
        'items': ('kstat.get[unix:0:vopstats_disk%(id)d:nread]', 'kstat.get[unix:0:vopstats_disk%(id)d:nwrite]'),
        'items_search': {'search': {'key_': 'kstat.get[unix:0:vopstats_*:n*]'}, 'searchWildcardsEnabled': True,
                         'limit': 2, 'sortfield': ['name'], 'sortorder': '???'},
        'items_search_fun': _zone_fs_items,
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'vm-disk-logical-throughput': {
        'desc': _('Aggregated disk throughput on the logical layer (with acceleration mechanisms included).'),
        'items': ('kstat.get[zone_vfs:{$ZONEID}::nread]', 'kstat.get[zone_vfs:{$ZONEID}::nwritten]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'vm-disk-logical-io': {
        'desc': _('Aggregated amount or read and write I/O operations on the logical layer '
                  '(with acceleration mechanisms included).'),
        'items': ('kstat.get[zone_vfs:{$ZONEID}::reads]', 'kstat.get[zone_vfs:{$ZONEID}::writes]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'vm-disk-physical-throughput': {
        'desc': _('Aggregated disk throughput on the physical (disk) layer.'),
        'items': ('kstat.get[zone_zfs:{$ZONEID}::nread]', 'kstat.get[zone_zfs:{$ZONEID}::nwritten]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'vm-disk-physical-io': {
        'desc': _('Aggregated amount of read and write I/O operations on the physical (disk) layer.'),
        'items': ('kstat.get[zone_zfs:{$ZONEID}::reads]', 'kstat.get[zone_zfs:{$ZONEID}::writes]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'vm-disk-io-operations': {
        'desc': _('Aggregated amount of disk I/O operations by latency on the logical layer '
                  '(with acceleration mechanisms included).'),
        'items': ('kstat.get[zone_vfs:{$ZONEID}::1s_ops]', 'kstat.get[zone_vfs:{$ZONEID}::10s_ops]',
                  'kstat.get[zone_vfs:{$ZONEID}::10ms_ops]', 'kstat.get[zone_vfs:{$ZONEID}::100ms_ops]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GRAPH_LINE_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
    },

})
