from django.views.i18n import JavaScriptCatalog
from django.views.decorators.http import last_modified
from django.utils import timezone


last_modified_date = timezone.now()

javascript_catalog = JavaScriptCatalog.as_view()


@last_modified(lambda req, **kw: last_modified_date)
def cached_javascript_catalog(request, domain='djangojs', packages=None):
    """
    https://docs.djangoproject.com/en/1.5/topics/i18n/translation/#note-on-performance
    """
    return javascript_catalog(request, domain, packages)
