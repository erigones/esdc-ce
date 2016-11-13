from dictdiffer import diff

from api.api_views import APIView


class VmDefineBaseView(APIView):
    """
    Common stuff for VmDefineView, VmDefineDiskView and VmDefineNicView.
    """
    _active = None
    _diff = None

    def is_full(self, data):
        return self.request.method == 'GET' and self.request.query_params.get('full', False)

    def is_extended(self, data):
        return self.request.method == 'GET' and self.request.query_params.get('extended', False)

    # noinspection PyUnusedLocal
    def is_active(self, data):
        return self.request.method == 'GET' and self.request.query_params.get('active', False)

    # noinspection PyUnusedLocal
    def is_diff(self, data):
        return self.request.method == 'GET' and self.request.query_params.get('diff', False)

    @property
    def active(self):
        if self._active is None:
            self._active = self.is_active(self.data)
        return self._active

    @property
    def diff(self):
        if self._diff is None:
            self._diff = self.is_diff(self.data)
        return self._diff

    @staticmethod
    def _diff_dicts(active, current, ignore=('changed',)):
        res = {}

        for t, key, value in diff(active, current, ignore=ignore):
            if t not in res:
                res[t] = {}

            if t == 'change':
                if isinstance(key, list):  # list value has changed
                    key = key[0]
                    value = (active[key], current[key])

                res[t][key] = value
            else:  # add, remove
                if key:  # list value has changed
                    if 'change' not in res:
                        res['change'] = {}
                    res['change'][key] = (active[key], current[key])
                else:
                    for k, v in value:
                        res[t][k] = v

        return res

    @staticmethod
    def _diff_lists(active, current, ignore=()):
        res = {}

        for t, key, value in diff(active, current, ignore=ignore):
            if t not in res:
                res[t] = {}

            if t == 'change':
                list_id, attr = key
                list_id += 1

                if list_id not in res[t]:
                    res[t][list_id] = {}

                res[t][list_id][attr] = value

            else:  # add, remove
                for list_id, full_value in value:
                    res[t][list_id + 1] = full_value

        return res
