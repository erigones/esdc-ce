from django.utils.translation import ugettext_noop as _


def _threshold_to_grid(val):
    """Return graph threshold configuration"""
    return {
        'markings': [
            {'color': '#FF0000', 'lineWidth': 1, 'yaxis': {'from': val, 'to': val}},
        ]
    }


def _mem_usage_cap(graph_options, node):
    """Add RAM usage threshold"""
    cap = node.ram

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
GRAPH_UPDATE_INTERVAL_LONG = 130
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
        'desc': _('Total compute node CPU consumed by the node.'),
        'items': ('system.cpu.util[,system,]', 'system.cpu.util[,user,]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'series': GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'cpu-jumps': {
        'desc': _('Number of context switches and interrupts on the node.'),
        'items': ('system.cpu.switches', 'system.cpu.intr'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GRAPH_LINE_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'cpu-load': {
        'desc': _('1-minute load average.'),
        'items': ['system.cpu.load[,avg1]'],
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'mem-usage': {
        'desc': _('Total compute node physical memory consumed by the node.'),
        'items': ('vm.memory.size[used]',),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byte', 'min': 0},
        },
        '_opts_fun': _mem_usage_cap,
    },

    'swap-usage': {
        'desc': _('Total compute node swap space used by the node.'),
        'items': ('system.swap.size[,used]',),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byte', 'min': 0},
        },
    },

    'storage-throughput': {
        'desc': _('The amount of read and written data on the zpool.'),
        'items': ('zpool.iostat[%(id)s,nread]', 'zpool.iostat[%(id)s,nwritten]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'storage-io': {
        'desc': _('The amount of read and write I/O operations performed on the zpool.'),
        'items': ('zpool.iostat[%(id)s,reads]', 'zpool.iostat[%(id)s,writes]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'storage-space': {
        'desc': _('ZFS zpool space usage by type.'),
        'items': ('zfs.usedds[%(id)s]', 'zfs.usedrefreserv[%(id)s]', 'zfs.usedsnap[%(id)s]'),
        'update_interval': GRAPH_UPDATE_INTERVAL_LONG,
        'history': 3,
        'options': {
            'series': GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byte', 'min': 0},
        },
    },

    'net-bandwidth': {
        'desc': _('The amount of received and sent network traffic over the network interface.'),
        'items': ('net.if.in[%(id)s]', 'net.if.out[%(id)s]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': 'bitRate', 'min': 0},
        },
    },

    'net-packets': {
        'desc': _('The number of received and sent packets through the network interface.'),
        'items': ('net.if.in[%(id)s,packets]', 'net.if.out[%(id)s,packets]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'yaxis': {'mode': None, 'min': 0},
        },
    },

})
