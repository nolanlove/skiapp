"""
URL configuration for resorts app.
"""
from django.urls import path
from . import views

app_name = 'resorts'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/search/', views.search_resorts, name='search'),
    path('api/resorts/', views.get_all_resorts, name='all_resorts'),
]

