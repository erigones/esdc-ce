class GraphItems(dict):
    """
    Graph Item Dictionary.
    """
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

    def get_options(self, item, *args, **kwargs):
        opts = self[item]
        fun = opts.pop('_opts_fun', None)

        if fun:
            opts = fun(opts, *args, **kwargs)

        return opts

    @staticmethod
    def _threshold_to_grid(val):
        """Return graph threshold configuration"""
        return {
            'markings': [
                {'color': '#FF0000', 'lineWidth': 1, 'yaxis': {'from': val, 'to': val}},
            ]
        }

    @classmethod
    def mem_usage_cap(cls, graph_options, obj):
        """Add RAM usage threshold"""
        cap = obj.ram

        if cap:
            graph_options['options'] = graph_options['options'].copy()
            graph_options['options']['grid'] = cls._threshold_to_grid(cap * 1048576)

        return graph_options

    @classmethod
    def cpu_usage_cap(cls, graph_options, obj):
        """Add CPU usage threshold"""
        cap = obj.vcpus_active

        if cap:
            graph_options['options'] = graph_options['options'].copy()
            graph_options['options']['grid'] = cls._threshold_to_grid(cap * 100)

        return graph_options

    @staticmethod
    def zone_fs_items(graph_options, item_id):
        """Return zabbix search params"""
        items_search = graph_options['items_search'].copy()
        items_search['sortorder'] = item_id  # 0 - ASC, 1 - DESC

        return items_search
