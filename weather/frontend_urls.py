from django.urls import path
from .frontend_views import DashboardView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
]
