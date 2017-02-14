def parse_graph_node(node, graph):
    """
    Validate graph identificator and return graph category and item id.

    :param node: Node for which the graph is being retrieved
    :type node: `class vms.models.Node`
    :param str graph: Name of the graph to retrieve

    :return: tuple (graph category, item id)
    """
    _graph = str(graph).split('-')
    try:
        item_id = int(_graph[-1])
    except ValueError:
        cat = graph
        item_id = None
    else:
        cat = '-'.join(_graph[:-1])
        item_id -= 1

# TODO implement Node specific code for networks and disks
#    if item_id is not None:
#        if item_id < 0:
#            cat = None
#        elif _graph[0] in ('nic', 'net'):
#            try:
#                item_id = node
#            except IndexError:
#                cat = None
#        elif _graph[0] in ('disk', 'hdd', 'fs'):
#            try:
#                item_id = node
#            except IndexError:
#                cat = None
#        else:
#            cat = None

    return cat, item_id
