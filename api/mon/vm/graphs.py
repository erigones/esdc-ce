from django.utils.translation import ugettext_noop as _

from api.mon.graphs import GraphItems
from vms.models import Vm


GRAPH_ITEMS = GraphItems({
    'cpu-usage': {
        'desc': _('Total compute node CPU consumed by the VM.'),
        'items': ('vm.cpu.sys', 'vm.cpu.user'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
        '_opts_fun': GraphItems.cpu_usage_cap,
    },

    'cpu-waittime': {
        'desc': _('Total amount of time spent in CPU run queue by the VM.'),
        'items': ('vm.cpu.wait',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': 'second', 'min': 0},
        },
    },

    'cpu-load': {
        'desc': _('1-minute load average.'),
        'items': ('kstat.get[zones::{HOST.NAME}:avenrun_1min]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'mem-usage': {
        'desc': _('Total compute node physical memory consumed by the VM.'),
        'items': ('kstat.get[memory_cap::{HOST.NAME}:rss]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byte', 'min': 0},
        },
        '_opts_fun': GraphItems.mem_usage_cap,
    },

    'swap-usage': {
        'desc': _('Total compute node swap space used by the VM.'),
        'items': ('kstat.get[memory_cap::{HOST.NAME}:swap]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byte', 'min': 0},
        },
    },

    'net-bandwidth': {
        'desc': _('The amount of received and sent network traffic through the virtual network interface.'),
        'items': ('vm.net[net%(id)d,rbytes64]', 'vm.net[net%(id)d,obytes64]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'bitRate', 'min': 0},
        },
    },

    'net-packets': {
        'desc': _('The amount of received and sent packets through the virtual network interface.'),
        'items': ('vm.net[net%(id)d,ipackets64]', 'vm.net[net%(id)d,opackets64]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'disk-throughput': {
        'desc': _('The amount of written and read data on the virtual hard drive.'),
        'required_ostype': Vm.KVM,
        'items': ('vm.disk.io[disk%(id)d,read]', 'vm.disk.io[disk%(id)d,written]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'disk-io': {
        'desc': _('The amount of write and read I/O operations performed on the virtual hard drive.'),
        'required_ostype': Vm.KVM,
        'items': ('vm.disk.io[disk%(id)d,reads]', 'vm.disk.io[disk%(id)d,writes]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
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
        'items_search_fun': GraphItems.zone_fs_items,
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
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
        'items_search_fun': GraphItems.zone_fs_items,
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'vm-disk-logical-throughput': {
        'desc': _('Aggregated disk throughput on the logical layer (with acceleration mechanisms included).'),
        'items': ('kstat.get[zone_vfs::{HOST.NAME}:nread]', 'kstat.get[zone_vfs::{HOST.NAME}:nwritten]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'vm-disk-logical-io': {
        'desc': _('Aggregated amount or read and write I/O operations on the logical layer '
                  '(with acceleration mechanisms included).'),
        'items': ('kstat.get[zone_vfs::{HOST.NAME}:reads]', 'kstat.get[zone_vfs::{HOST.NAME}:writes]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'vm-disk-physical-throughput': {
        'desc': _('Aggregated disk throughput on the physical (disk) layer.'),
        'items': ('kstat.get[zone_zfs::{HOST.NAME}:nread]', 'kstat.get[zone_zfs::{HOST.NAME}:nwritten]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'vm-disk-physical-io': {
        'desc': _('Aggregated amount of read and write I/O operations on the physical (disk) layer.'),
        'items': ('kstat.get[zone_zfs::{HOST.NAME}:reads]', 'kstat.get[zone_zfs::{HOST.NAME}:writes]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'vm-disk-io-operations': {
        'desc': _('Aggregated amount of disk I/O operations by latency on the logical layer '
                  '(with acceleration mechanisms included).'),
        'items': ('kstat.get[zone_vfs::{HOST.NAME}:1s_ops]', 'kstat.get[zone_vfs::{HOST.NAME}:10s_ops]',
                  'kstat.get[zone_vfs::{HOST.NAME}:10ms_ops]', 'kstat.get[zone_vfs::{HOST.NAME}:100ms_ops]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_LINE_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
    },

})
