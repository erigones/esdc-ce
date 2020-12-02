from django.urls import path, include

urlpatterns = [
    path('vm/', include('api.mon.vm.urls')),
    path('node/', include('api.mon.node.urls')),
    path('alert/', include('api.mon.alerting.urls')),
    path('action/', include('api.mon.alerting.action.urls')),
    path('', include('api.mon.base.urls')),
]
