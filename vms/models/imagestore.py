from hashlib import md5
from frozendict import frozendict
from django.utils.translation import ugettext_lazy as _
from django.utils.text import Truncator
from django.utils.dateparse import parse_datetime
from django.core.cache import cache
# noinspection PyUnresolvedReferences
from django.utils.six.moves.urllib.parse import urljoin

# noinspection PyProtectedMember
from vms.models.base import _DummyModel
from vms.models.dc import DefaultDc
from vms.models.image import Image


class ImageStoreObject(dict):
    """
    Represents one image found in ImageStore.images.
    """
    OSTYPE = frozendict(Image.OSTYPE)

    def __init__(self, manifest, manifest_url):
        dict.__init__(self)

        self['manifest'] = manifest
        self['manifest_url'] = manifest_url
        self['uuid'] = manifest['uuid']
        self['name'] = manifest['name']
        self['version'] = manifest.get('version', '')
        self['created'] = parse_datetime(manifest.get('published_at', '')) or ''
        self['ostype'] = Image.os_to_ostype(manifest)
        self['desc'] = manifest.get('description', '')
        self['homepage'] = manifest.get('homepage')
        self['size'] = manifest.get('image_size', Image.DEFAULT_SIZE)
        self['state'] = manifest.get('state', '')

        try:
            self['download_size'] = manifest['files'][0]['size']
        except (KeyError, IndexError):
            self['download_size'] = 0

    def get_ostype_display(self):
        return self.OSTYPE.get(self['ostype'])

    @property
    def web_data(self):
        """Return dict used in web templates"""
        manifest = self['manifest']
        tags = manifest.get('tags', {})

        return {
            'name': manifest['name'],
            'alias': manifest['name'],
            'version': manifest['version'],
            'desc': manifest.get('description', '')[:128],
            'dc_bound': False,
            'tags': tags.get(Image.TAGS_KEY, []),
            'deploy': tags.get('deploy', False),
            'resize': tags.get('resize', self['ostype'] in Image.ZONE),
            'manifest_url': self['manifest_url'],
        }


class ImageStore(_DummyModel):
    """
    Dummy model for representing a specific instance of a image repository (a.k.a. imagestore).
    """
    FIELDS = (
        ('name', None),
        ('url', None),
        ('last_update', None),
        ('image_count', 0),
        ('error', None),
    )
    CACHE_PREFIX_REPO = 'imagestore:'
    CACHE_SUFFIX_IMAGES = ':images'
    IMAGE_LIST_URI = '/images'
    IMAGE_URI = '/images/%s'

    # noinspection PyPep8Naming
    class Meta:
        # Required for api.exceptions.ObjectNotFound
        verbose_name_raw = _('ImageStore')
        app_label = 'vms'

    def __init__(self, name, url=None):
        self.name = name
        data = cache.get(self._cache_key_repo)

        if not data:
            data = dict(self.FIELDS)
            data.update(name=name, url=url)

        super(ImageStore, self).__init__(data)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.name)

    @staticmethod
    def get_repositories():
        return DefaultDc().settings.VMS_IMAGE_REPOSITORIES

    @classmethod
    def all(cls, repositories):
        return [cls(repo, url=url) for repo, url in repositories.items()]

    @property
    def _cache_key_repo(self):
        return self.CACHE_PREFIX_REPO + self.name

    @property
    def _cache_key_images(self):
        return self._cache_key_repo + self.CACHE_SUFFIX_IMAGES

    @property
    def images(self):
        return cache.get(self._cache_key_images) or []

    def images_filter(self, created_since=None, limit=None):
        images = self.images

        if created_since:
            images = [img for img in images if img['created'] > created_since]

        if limit:
            images = images[:limit]

        return images

    def save_images(self, images):
        cache.set(
            self._cache_key_images,
            [ImageStoreObject(img, self.get_image_manifest_url(img['uuid'])) for img in images]
        )

    def delete_images(self):
        cache.delete(self._cache_key_images)

    def save(self, images=None):
        cache.set(self._cache_key_repo, self)

        if images:
            self.save_images(images)

    def delete(self):
        self.delete_images()
        cache.delete(self._cache_key_repo)

    def get_images_url(self):
        return urljoin(self.url, self.IMAGE_LIST_URI)

    def get_image_manifest_url(self, uuid):
        return urljoin(self.url, self.IMAGE_URI % uuid)

    @property
    def pk(self):  # Required by task_log
        assert self.url
        return md5(self.url).hexdigest()

    @property
    def log_name(self):  # Required by task_log
        return Truncator(self.url).chars(32)

    @property
    def log_alias(self):  # Required by task_log
        return self.name
