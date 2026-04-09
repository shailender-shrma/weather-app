from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FetchDataView,
    MetaView,
    ParameterViewSet,
    RegionViewSet,
    WeatherDatasetViewSet,
    WeatherRecordViewSet,
)

router = DefaultRouter()
router.register(r'parameters', ParameterViewSet, basename='parameter')
router.register(r'regions', RegionViewSet, basename='region')
router.register(r'datasets', WeatherDatasetViewSet, basename='dataset')
router.register(r'records', WeatherRecordViewSet, basename='record')

urlpatterns = [
    path('', include(router.urls)),
    path('fetch/', FetchDataView.as_view(), name='fetch-data'),
    path('meta/', MetaView.as_view(), name='meta'),
]
