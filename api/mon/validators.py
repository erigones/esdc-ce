def parse_graph_vm(vm, graph):
    """
    Validate graph identificator and return graph category and item id.

    :param vm: VM for which the graph is being retrieved
    :type vm: `class vms.models.Vm`
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

    if item_id is not None:
        if item_id < 0:
            cat = None
        elif _graph[0] in ('nic', 'net'):
            try:
                item_id = vm.get_real_nic_id(vm.json_active_get_nics()[item_id])
            except IndexError:
                cat = None
        elif _graph[0] in ('disk', 'hdd', 'fs'):
            try:
                item_id = vm.get_real_disk_id(vm.json_active_get_disks()[item_id])
            except IndexError:
                cat = None
        else:
            cat = None

    return cat, item_id
