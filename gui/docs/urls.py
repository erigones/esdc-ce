from django.conf.urls import url

from gui.docs.views import faq, api, user_guide

urlpatterns = [
    url(r'^faq/$', faq, name='faq'),
    url(r'^api/$', api, name='api_docs'),
    url(r'^user-guide/$', user_guide, name='user_guide'),
]
