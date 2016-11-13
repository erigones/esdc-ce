from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.support.views',

    url(r'^add_ticket/$', 'add_ticket', name='add_ticket'),
    url(r'^add_ticket/submit/$', 'add_ticket_submit', name='add_ticket_submit'),
)
