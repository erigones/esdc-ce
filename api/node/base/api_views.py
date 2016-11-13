from api.api_views import APIView
from api.task.response import SuccessTaskResponse
from api.node.utils import get_node, get_nodes
from api.node.base.serializers import NodeSerializer, ExtendedNodeSerializer


class NodeView(APIView):
    """Read-only node view"""
    dc_bound = False
    order_by_default = order_by_fields = ('hostname',)

    def get(self, hostname, many=False):
        request = self.request
        sr = ('owner',)

        if self.extended:
            ser_class = ExtendedNodeSerializer
            pr = ('dc',)
            extra = {'select': ExtendedNodeSerializer.extra_select}
        else:
            ser_class = NodeSerializer
            pr = ()
            extra = None

        if many:
            if self.full or self.extended:
                nodes = get_nodes(request, sr=sr, pr=pr, extra=extra, order_by=self.order_by)

                if nodes:
                    # noinspection PyUnresolvedReferences
                    res = ser_class(nodes, many=True).data
                else:
                    res = []
            else:
                res = list(get_nodes(request, order_by=self.order_by).values_list('hostname', flat=True))

        else:
            node = get_node(request, hostname, sr=sr, pr=pr, extra=extra)
            # noinspection PyUnresolvedReferences
            res = ser_class(node).data

        return SuccessTaskResponse(request, res, dc_bound=False)
