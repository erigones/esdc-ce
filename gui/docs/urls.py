from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.docs.views',

    url(r'^faq/$', 'faq', name='faq'),
    url(r'^api/$', 'api', name='api_docs'),
    url(r'^user-guide/$', 'user_guide', name='user_guide'),
)
