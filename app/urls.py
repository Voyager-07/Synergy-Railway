from django.urls import path
from django.views.generic import TemplateView

from .views import *

urlpatterns = [
    path('', index, name='index'),
    path('about', about, name='about'),
    path('update-profile/', update_profile, name='update_profile'),
    path('profile/', profile, name='profile'),
    path('aggregator/', aggregator, name='aggregator'),
]
