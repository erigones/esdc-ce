from django.utils.translation import ugettext_noop as _

from api.mon.graphs import GraphItems


GRAPH_ITEMS = GraphItems({
    'cpu-usage': {
        'desc': _('Total CPU utilisation on the compute node.'),
        'items': ('system.cpu.util[,system,]', 'system.cpu.util[,user,]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'cpu-jumps': {
        'desc': _('Number of context switches and interrupts on the compute node.'),
        'items': ('system.cpu.switches', 'system.cpu.intr'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_LINE_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'cpu-load': {
        'desc': _('1-minute load average.'),
        'items': ['system.cpu.load[,avg1]'],
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'mem-usage': {
        'desc': _('Total physical memory consumed by the compute node.'),
        'items': ('vm.memory.size[used]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byte', 'min': 0},
        },
        '_opts_fun': GraphItems.mem_usage_cap,
    },

    'swap-usage': {
        'desc': _('Total swap space used by the compute node.'),
        'items': ('system.swap.size[,used]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byte', 'min': 0},
        },
    },

    'storage-throughput': {
        'desc': _('The amount of read and written data on the zpool.'),
        'items': ('zpool.iostat[%(id)s,nread]', 'zpool.iostat[%(id)s,nwritten]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'storage-io': {
        'desc': _('The amount of read and write I/O operations performed on the zpool.'),
        'items': ('zpool.iostat[%(id)s,reads]', 'zpool.iostat[%(id)s,writes]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'storage-space': {
        'desc': _('ZFS zpool space usage by type.'),
        'items': ('zfs.usedds[%(id)s]', 'zfs.usedrefreserv[%(id)s]', 'zfs.usedsnap[%(id)s]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL_LONG,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byte', 'min': 0},
        },
    },

    'net-bandwidth': {
        'desc': _('The amount of received and sent network traffic over the network interface.'),
        'items': ('net.if.in[%(id)s]', 'net.if.out[%(id)s]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'bitRate', 'min': 0},
        },
    },

    'net-packets': {
        'desc': _('The number of received and sent packets through the network interface.'),
        'items': ('net.if.in[%(id)s,packets]', 'net.if.out[%(id)s,packets]'),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'vm-cpu-usage': {
        'desc': _('CPU consumed by each virtual machine on the compute node.'),
        'items': ('vm.cpu.total',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
        'add_host_name': True,
    },

    'vm-mem-usage': {
        'desc': _('Physical memory consumed by each virtual machine on the compute node.'),
        'items': ('kstat.get[memory_cap::{$UUID_SHORT}:rss]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byte', 'min': 0},
        },
        '_opts_fun': GraphItems.mem_usage_cap,
        'add_host_name': True,
    },

    'vm-disk-logical-throughput-reads': {
        'desc': _('Amount of data read on the logical layer (with acceleration mechanisms included) '
                  'by each virtual machine on the compute node.'),
        'items': ('kstat.get[zone_vfs::{$UUID_SHORT}:nread]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
        'add_host_name': True,
    },

    'vm-disk-logical-throughput-writes': {
        'desc': _('Amount of data written on the logical layer (with acceleration mechanisms included) '
                  'by each virtual machine on the compute node.'),
        'items': ('kstat.get[zone_vfs::{$UUID_SHORT}:nwritten]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
        'add_host_name': True,
    },

    'vm-disk-logical-io-reads': {
        'desc': _('Number of read operation performed on the logical layer (with acceleration mechanisms included) '
                  'by each virtual machine on the compute node.'),
        'items': ('kstat.get[zone_vfs::{$UUID_SHORT}:reads]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
        'add_host_name': True,
    },

    'vm-disk-logical-io-writes': {
        'desc': _('Number of write operation performed on the logical layer (with acceleration mechanisms included) '
                  'by each virtual machine on the compute node.'),
        'items': ('kstat.get[zone_vfs::{$UUID_SHORT}:writes]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
        'add_host_name': True,
    },

    'vm-disk-physical-throughput-reads': {
        'desc': _('Amount of data read on the physical (disk) layer '
                  'by each virtual machine on the compute node.'),
        'items': ('kstat.get[zone_zfs::{$UUID_SHORT}:nread]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
        'add_host_name': True,
    },

    'vm-disk-physical-throughput-writes': {
        'desc': _('Amount of data written on the physical (disk) layer '
                  'by each virtual machine on the compute node.'),
        'items': ('kstat.get[zone_zfs::{$UUID_SHORT}:nwritten]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
        'add_host_name': True,
    },

    'vm-disk-physical-io-reads': {
        'desc': _('Number of read operation performed on the physical (disk) layer '
                  'by each virtual machine on the compute node.'),
        'items': ('kstat.get[zone_zfs::{$UUID_SHORT}:reads]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
        'add_host_name': True,
    },

    'vm-disk-physical-io-writes': {
        'desc': _('Number of write operation performed on the physical (disk) layer '
                  'by each virtual machine on the compute node.'),
        'items': ('kstat.get[zone_zfs::{$UUID_SHORT}:writes]',),
        'update_interval': GraphItems.GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GraphItems.GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
        'add_host_name': True,
    },

})
