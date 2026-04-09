from rest_framework import serializers
from .models import Parameter, Region, WeatherDataset, WeatherRecord


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = ['id', 'code', 'display_name', 'unit', 'description']


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['id', 'code', 'display_name']


class WeatherDatasetSerializer(serializers.ModelSerializer):
    parameter = ParameterSerializer(read_only=True)
    region = RegionSerializer(read_only=True)

    class Meta:
        model = WeatherDataset
        fields = ['id', 'parameter', 'region', 'last_fetched', 'source_url', 'row_count']


class WeatherRecordSerializer(serializers.ModelSerializer):
    parameter_code = serializers.CharField(source='dataset.parameter.code', read_only=True)
    parameter_unit = serializers.CharField(source='dataset.parameter.unit', read_only=True)
    region_code = serializers.CharField(source='dataset.region.code', read_only=True)

    class Meta:
        model = WeatherRecord
        fields = [
            'id', 'year', 'parameter_code', 'parameter_unit', 'region_code',
            'jan', 'feb', 'mar', 'apr', 'may', 'jun',
            'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            'annual',
        ]


class WeatherRecordCompactSerializer(serializers.ModelSerializer):
    """Compact serializer returning monthly values as a list for charting."""
    monthly = serializers.SerializerMethodField()

    class Meta:
        model = WeatherRecord
        fields = ['year', 'monthly', 'annual']

    def get_monthly(self, obj):
        fields = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        return [getattr(obj, f) for f in fields]


class AnnualSeriesSerializer(serializers.ModelSerializer):
    """Minimal serializer for annual time-series charts."""
    class Meta:
        model = WeatherRecord
        fields = ['year', 'annual']


class FetchRequestSerializer(serializers.Serializer):
    """Input for the data-fetch endpoint."""
    parameter = serializers.ChoiceField(choices=[
        'Tmax', 'Tmin', 'Tmean', 'Sunshine',
        'Rainfall', 'Raindays1mm', 'AirFrost',
    ])
    region = serializers.ChoiceField(choices=[
        'UK', 'England', 'Wales', 'Scotland', 'Northern_Ireland',
        'England_and_Wales', 'England_N', 'England_S',
        'Scotland_N', 'Scotland_E', 'Scotland_W',
        'EW_E', 'EW_W', 'Midlands', 'East_Anglia',
    ])
