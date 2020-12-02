from django.urls import path

from gui.dc.node.views import dc_node_list, dc_node_form

urlpatterns = [
    path('', dc_node_list, name='dc_node_list'),
    path('form/', dc_node_form, name='dc_node_form'),
]
