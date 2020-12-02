from django.urls import path

from gui.support.views import add_ticket, add_ticket_submit

urlpatterns = [
    path('add_ticket/', add_ticket, name='add_ticket'),
    path('add_ticket/submit/', add_ticket_submit, name='add_ticket_submit'),
]
