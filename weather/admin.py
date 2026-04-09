from django.contrib import admin
from .models import Parameter, Region, WeatherDataset, WeatherRecord


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ['code', 'display_name', 'unit']
    search_fields = ['code', 'display_name']


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['code', 'display_name']
    search_fields = ['code', 'display_name']


@admin.register(WeatherDataset)
class WeatherDatasetAdmin(admin.ModelAdmin):
    list_display = ['parameter', 'region', 'row_count', 'last_fetched']
    list_filter = ['parameter', 'region']
    readonly_fields = ['last_fetched', 'source_url', 'row_count']


@admin.register(WeatherRecord)
class WeatherRecordAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'year', 'annual']
    list_filter = ['dataset__parameter', 'dataset__region']
    search_fields = ['year']
    ordering = ['dataset', '-year']
