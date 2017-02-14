from django.utils.translation import ugettext_noop as _


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
GRAPH_STACK_SERIES = {
    'stack': True,
    'lines': {
        'fillColor': {'colors': [{'opacity': 0.6}]},
        'lineWidth': 0.2,
    }
}
GRAPH_ITEMS = _GraphItems({
    'cpu-usage': {
        'desc': _('Total compute node CPU consumed by the node.'),
        'items': ('system.cpu.util[,system,]', 'system.cpu.util[,user,]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GRAPH_STACK_SERIES,
            'yaxis': {'mode': None, 'min': 0},
        },
    },

    'cpu-jumps': {
        'desc': _('Total amount of time spent in CPU run queue by the node.'),
        'items': ('system.cpu.switches', 'system.cpu.intr'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 0,
        'options': {
            'yaxis': {'mode': 'second', 'min': 0},
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
        'items': ('zpool.iostat[%(zpool)s,nread]', 'zpool.iostat[%(zpool)s,nwritten]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

    'storage-io': {
        'desc': _('The amount of read and written data on the zpool.'),
        'items': ('zpool.iostat[%(zpool)s,nread]', 'zpool.iostat[%(zpool)s,nwritten]'),
        'update_interval': GRAPH_UPDATE_INTERVAL,
        'history': 3,
        'options': {
            'series': GRAPH_STACK_SERIES,
            'yaxis': {'mode': 'byteRate', 'min': 0},
        },
    },

})
