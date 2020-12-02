from django.urls import path

from gui.dc.group.views import dc_group_list, dc_group_form, admin_group_form

urlpatterns = [
    path('', dc_group_list, name='dc_group_list'),
    path('form/', dc_group_form, name='dc_group_form'),
    path('form/admin/', admin_group_form, name='admin_group_form'),
]
