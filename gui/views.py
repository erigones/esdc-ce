from django.views.i18n import javascript_catalog
from django.views.decorators.http import last_modified
from django.utils import timezone


last_modified_date = timezone.now()


@last_modified(lambda req, **kw: last_modified_date)
def cached_javascript_catalog(request, domain='djangojs', packages=None):
    """
    https://docs.djangoproject.com/en/1.5/topics/i18n/translation/#note-on-performance
    """
    return javascript_catalog(request, domain, packages)
