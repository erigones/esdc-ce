from django.conf.urls import url

from gui.support.views import add_ticket, add_ticket_submit

urlpatterns = [
    url(r'^add_ticket/$', add_ticket, name='add_ticket'),
    url(r'^add_ticket/submit/$', add_ticket_submit, name='add_ticket_submit'),
]
