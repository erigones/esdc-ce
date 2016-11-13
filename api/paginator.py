from collections import OrderedDict

from django.core.paginator import InvalidPage, Paginator as DjangoPaginator

from api.exceptions import NotFound
from api.utils.urls import replace_query_param


class Paginator(DjangoPaginator):
    """
    API paginator that has a get_response_results() method used in api_views via api.utils.get_pager().
    """
    page_query_param = 'page'
    invalid_page_message = 'Invalid page.'

    def __init__(self, request, object_list, per_page, **kwargs):
        super(Paginator, self).__init__(object_list, per_page, **kwargs)
        self.page = None
        self.request = request

    def get_page(self, page):
        try:
            self.page = self.page(page)
        except InvalidPage:
            raise NotFound(self.invalid_page_message)
        else:
            return self.page

    def get_next_link(self):
        if not self.page.has_next():
            return None

        url = self.request.build_absolute_uri()
        page_number = self.page.next_page_number()

        return replace_query_param(url, self.page_query_param, page_number)

    def get_previous_link(self):
        if not self.page.has_previous():
            return None

        url = self.request.build_absolute_uri()
        page_number = self.page.previous_page_number()

        if page_number == 1:
            return None

        return replace_query_param(url, self.page_query_param, page_number)

    def get_response_results(self, results):
        return OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', results),
        ])


def get_pager(request, qs, per_page=100, page=None):
    """
    Return our paginator.page object for a queryset.
    """
    paginator = Paginator(request, qs, per_page)

    if page is None:
        page = request.query_params.get('page', 1)

    return paginator.get_page(page)
