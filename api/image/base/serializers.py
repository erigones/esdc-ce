from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from api.validators import validate_owner, validate_dc_bound
from api.utils.http import HttpClient, RequestException, TooLarge
from api.vm.utils import get_owners
from gui.models import User
from vms.models import Image


class ImageSerializer(s.InstanceSerializer):
    """
    vms.models.Image
    Also used in api.dc.image.serializers.
    """
    _model_ = Image
    _update_fields_ = ('alias', 'version', 'dc_bound', 'owner', 'access', 'desc', 'resize', 'deploy', 'tags')
    # TODO: 'nic_model', 'disk_model'
    _default_fields_ = ('name', 'alias', 'owner')

    name = s.RegexField(r'^[A-Za-z0-9][A-Za-z0-9\._-]*$', max_length=32)
    alias = s.SafeCharField(max_length=32)
    version = s.SafeCharField(max_length=16, default='1.0')
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects)
    access = s.IntegerChoiceField(choices=Image.ACCESS, default=Image.PRIVATE)
    desc = s.SafeCharField(max_length=128, required=False)
    ostype = s.IntegerChoiceField(choices=Image.OSTYPE, read_only=True)
    size = s.IntegerField(read_only=True)
    resize = s.BooleanField(default=False)
    deploy = s.BooleanField(default=False)
    # nic_model = s.ChoiceField(choices=Vm.NIC_MODEL)   # KVM only
    # disk_model = s.ChoiceField(choices=Vm.DISK_MODEL)  # KVM only
    tags = s.TagField(required=False, default=[])
    dc_bound = s.BooleanField(source='dc_bound_bool', default=True)
    status = s.IntegerChoiceField(choices=Image.STATUS, read_only=True, required=False)
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, img, *args, **kwargs):
        super(ImageSerializer, self).__init__(request, img, *args, **kwargs)

        if not kwargs.get('many', False):
            self.update_manifest = True
            self._dc_bound = img.dc_bound
            self.fields['owner'].queryset = get_owners(request, all=True)

    def _normalize(self, attr, value):
        if attr == 'dc_bound':
            return self._dc_bound
        # noinspection PyProtectedMember
        return super(ImageSerializer, self)._normalize(attr, value)

    def validate_owner(self, attrs, source):
        """Cannot change owner while pending tasks exist"""
        validate_owner(self.object, attrs.get(source, None), _('Image'))

        return attrs

    def validate_dc_bound(self, attrs, source):
        try:
            value = bool(attrs[source])
        except KeyError:
            pass
        else:
            if value != self.object.dc_bound_bool:
                self._dc_bound = validate_dc_bound(self.request, self.object, value, _('Image'))

        return attrs

    def validate(self, attrs):
        manifest_keys = {'name', 'alias', 'version', 'access', 'desc', 'tags'}

        if manifest_keys.isdisjoint(attrs.keys()):
            self.update_manifest = False

        try:
            alias = attrs['alias']
        except KeyError:
            alias = self.object.alias

        try:
            version = attrs['version']
        except KeyError:
            version = self.object.version

        qs = Image.objects

        if self.object.pk:
            qs = qs.exclude(pk=self.object.pk)

        if qs.filter(alias__iexact=alias, version=version).exists():
            self._errors['alias'] = s.ErrorList([_('This alias is already in use. '
                                                   'Please supply a different alias or version.')])

        if self.request.method == 'POST' and self._dc_bound:
            limit = self._dc_bound.settings.VMS_IMAGE_LIMIT

            if limit is not None:
                if Image.objects.filter(dc_bound=self._dc_bound).count() >= int(limit):
                    raise s.ValidationError(_('Maximum number of server disk images reached'))

        return attrs


class ExtendedImageSerializer(ImageSerializer):
    dcs = s.DcsField()


class ImportImageSerializer(s.Serializer):
    manifest_url = s.URLField(max_length=1024)
    file_url = s.URLField(max_length=1024, required=False)

    def __init__(self, img, *args, **kwargs):
        self.img = img
        self.img_file_url = None
        self.img_manifest_url = None
        super(ImportImageSerializer, self).__init__(*args, **kwargs)

    # noinspection PyAttributeOutsideInit
    def validate_manifest_url(self, attrs, source):
        try:
            url = attrs[source]
        except KeyError:
            return attrs

        img = self.img

        try:
            req = HttpClient(url)
            res = req.get(timeout=5, max_size=8192)
        except RequestException as e:
            raise s.ValidationError(_('Image manifest URL is unreachable (%s).') % e)

        try:
            self.manifest = manifest = res.json()
        except ValueError:
            raise s.ValidationError(_('Could not parse image manifest.'))

        try:
            self.img_file = manifest['files'][0]
            img.uuid = manifest['uuid']
            img.version = manifest['version']
            img.ostype = Image.os_to_ostype(manifest)
            img.size = int(manifest.get('image_size', Image.DEFAULT_SIZE))
            img.desc = manifest.get('description', '')[:128]
            tags = manifest.pop('tags', {})
            img.tags = tags.get(Image.TAGS_KEY, [])
            img.deploy = tags.get('deploy', False)
            img.resize = tags.get('resize', img.ostype in img.ZONE)
        except Exception:
            raise s.ValidationError(_('Invalid image manifest.'))

        if len(manifest['files']) > 1:
            raise s.ValidationError('Multiple files inside manifest are not supported.')

        if img.uuid:
            try:
                x = Image.objects.only('name').get(uuid=img.uuid)
            except Image.DoesNotExist:
                pass
            else:
                raise s.ValidationError(_('Image UUID is already registered by image "%(name)s".') % {'name': x.name})

        return attrs

    def validate(self, attrs):
        self.img_manifest_url = attrs['manifest_url']
        file_url = attrs.get('file_url', None)

        if not file_url:
            file_url = self.img_manifest_url.strip('/') + '/file'

        self.img_file_url = file_url

        try:
            req_file = HttpClient(file_url)
            req_file.get(timeout=5, max_size=32)
        except TooLarge:
            pass
        except RequestException as e:
            self._errors['file_url'] = s.ErrorList([_('Image file URL is unreachable (%s).') % e])

        return attrs

    def detail_dict(self, **kwargs):
        return {'manifest_url': self.img_manifest_url, 'file_url': self.img_file_url}
