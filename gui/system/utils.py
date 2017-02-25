from vms.utils import AttrDict


class GraphItem(AttrDict):
    """
    Representation of one item in a pie chart.
    """
    def __init__(self, label, data, **options):
        dict.__init__(self)
        self['label'] = label
        self['data'] = data
        self.update(options)
