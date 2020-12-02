from django.urls import path

from gui.docs.views import faq, api, user_guide

urlpatterns = [
    path('faq/', faq, name='faq'),
    path('api/', api, name='api_docs'),
    path('user-guide/', user_guide, name='user_guide'),
]
