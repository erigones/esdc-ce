import hashlib
import itertools
from operator import itemgetter
from frozendict import frozendict
from collections import OrderedDict
from django.utils.translation import ugettext_lazy as _
from django.utils.text import Truncator
from django.utils.dateparse import parse_datetime
from django.core.cache import cache
from django.utils.six import iteritems
# noinspection PyUnresolvedReferences
from django.utils.six.moves.urllib.parse import urljoin

# noinspection PyProtectedMember
from vms.models.base import _DummyDataModel
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
            'resize': tags.get('resize', self['ostype'] in Image.ZONE_OSTYPES),
            'manifest_url': self['manifest_url'],
        }


class ImageStore(_DummyDataModel):
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
    IMAGE_LIST_URI = 'images'
    IMAGE_URI = 'images/%s'

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

        super().__init__(data)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.name)

    @staticmethod
    def get_repositories(include_image_vm=False):
        from vms.models.image import ImageVm  # circular imports

        repos = OrderedDict(sorted(iteritems(DefaultDc().settings.VMS_IMAGE_REPOSITORIES)))
        image_vm = ImageVm()

        if include_image_vm and image_vm and image_vm.has_ip():
            repos[image_vm.repo_name] = image_vm.repo_url

        return repos

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

    def images_filter(self, created_since=None, limit=None, excluded_ostypes=()):
        def apply_filters(filters):
            def fun(image):
                return all(filter_(image) for filter_ in filters)
            return fun
        active_filters = []

        if created_since:
            active_filters.append(lambda img: img['created'] > created_since)

        if excluded_ostypes:
            active_filters.append(lambda img: img['ostype'] not in excluded_ostypes)

        images = filter(apply_filters(active_filters), self.images)

        if limit:
            images = itertools.islice(images, limit)

        return images

    @staticmethod
    def _ordering_newest_first(images):
        return sorted(images, key=itemgetter('created'), reverse=True)

    def save_images(self, images, order_fun=None):
        if not order_fun:
            order_fun = self._ordering_newest_first

        cache.set(
            self._cache_key_images,
            order_fun(ImageStoreObject(img, self.get_image_manifest_url(img['uuid'])) for img in images)
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

    @classmethod
    def get_content_type(cls):  # Required by task_log
        return None

    # noinspection PyUnusedLocal
    @classmethod
    def get_object_type(cls, content_type=None):  # Required by task_log
        return 'imagestore'

    @property
    def pk(self):  # Required by task_log
        assert self.url
        return hashlib.md5(self.url.encode()).hexdigest()

    @property
    def log_name(self):  # Required by task_log
        return Truncator(self.url).chars(32)

    @property
    def log_alias(self):  # Required by task_log
        return self.name
