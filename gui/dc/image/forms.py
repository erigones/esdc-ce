from django import forms
from django.utils.translation import ugettext_lazy as _

from api.dc.image.views import dc_image
from api.image.base.views import image_manage
from api.vm.utils import get_owners
from gui.forms import SerializerForm
from gui.fields import TagField
from gui.widgets import TagWidget
from vms.models import Image, TagVm, Vm


class ImageForm(SerializerForm):
    """
    Create or remove DC<->Image link by calling dc_image.
    """
    _api_call = dc_image

    name = forms.ChoiceField(label=_('Image'), required=True,
                             widget=forms.Select(attrs={'class': 'input-select2 narrow disable_created2'}))

    def __init__(self, request, images, *args, **kwargs):
        super(ImageForm, self).__init__(request, None, *args, **kwargs)
        self.fields['name'].choices = images.values_list('name', 'alias')

    def _final_data(self, data=None):
        return {}


class _ImageForm(SerializerForm):
    """
    Base class used by AdminImageForm below and servers.forms.ImageForm.
    """
    name = forms.CharField(label=_('Name'), max_length=32, required=True,
                           widget=forms.TextInput(attrs={'class': 'input-transparent narrow disable_created',
                                                         'required': 'required', 'pattern': '[A-Za-z0-9._-]+'}))
    alias = forms.CharField(label=_('Alias'), required=True, max_length=32,
                            widget=forms.TextInput(attrs={'class': 'input-transparent narrow', 'required': 'required'}))
    version = forms.CharField(label=_('Version'), required=False, max_length=16,
                              widget=forms.TextInput(attrs={'class': 'input-transparent narrow',
                                                            'required': 'required'}))
    owner = forms.ChoiceField(label=_('Owner'), required=False,
                              widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    access = forms.TypedChoiceField(label=_('Access'), required=False, coerce=int, choices=Image.ACCESS,
                                    widget=forms.Select(attrs={'class': 'narrow input-select2'}))
    desc = forms.CharField(label=_('Description'), max_length=128, required=False,
                           widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    resize = forms.BooleanField(label=_('Resizable?'), required=False,
                                help_text=_('Image is able to resize the disk during '
                                            'an initial start or deploy process.'),
                                widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    deploy = forms.BooleanField(label=_('Shutdown after deploy?'), required=False,
                                help_text=_('Image is able to shut down the server after '
                                            'an initial start and successful deploy.'),
                                widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))
    tags = TagField(label=_('Tags'), required=False,
                    help_text=_('Tags will be inherited by servers which will use this image.'),
                    widget=TagWidget(attrs={'class': 'tags-select2 narrow'}))

    def __init__(self, request, img, *args, **kwargs):
        super(_ImageForm, self).__init__(request, img, *args, **kwargs)
        self.fields['owner'].choices = get_owners(request).values_list('username', 'username')
        self.fields['tags'].tag_choices = TagVm.objects.distinct().filter(
            content_object__in=Vm.objects.filter(dc=request.dc)
        ).order_by('tag__name').values_list('tag__name', flat=True)


class AdminImageForm(_ImageForm):
    """
    Update or delete disk image by calling image_manage.
    """
    _api_call = image_manage

    # URLs are used only by import (POST), otherwise hidden via JS
    manifest_url = forms.URLField(label=_('Manifest URL'), required=False,
                                  widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    file_url = forms.URLField(label=_('Image file URL'), required=False,
                              widget=forms.TextInput(attrs={'class': 'input-transparent wide', 'required': ''}))
    dc_bound = forms.BooleanField(label=_('DC-bound?'), required=False,
                                  widget=forms.CheckboxInput(attrs={'class': 'normal-check'}))

    def __init__(self, request, img, *args, **kwargs):
        super(AdminImageForm, self).__init__(request, img, *args, **kwargs)

        if not request.user.is_staff:
            self.fields['dc_bound'].widget.attrs['disabled'] = 'disabled'

    def _initial_data(self, request, obj):
        return obj.web_data_admin

    def _final_data(self, data=None):
        data = super(AdminImageForm, self)._final_data(data=data)

        if self.action == 'create':  # Add dc parameter when doing POST (required by api.db.utils.get_virt_object)
            data['dc'] = self._request.dc.name
        else:
            data.pop('manifest_url', None)
            data.pop('file_url', None)

        return data
