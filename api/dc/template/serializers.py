from api.template.base.serializers import TemplateSerializer as _TemplateSerializer


class TemplateSerializer(_TemplateSerializer):
    """
    Read-only version of TemplateSerializer
    """
    _update_fields_ = ()

    # noinspection PyUnusedLocal
    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        return {'dc': self.request.dc}
