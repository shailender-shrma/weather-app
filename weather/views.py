import logging

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Parameter, Region, WeatherDataset, WeatherRecord
from .parsers import VALID_PARAMETERS, VALID_REGIONS, fetch_and_parse
from .serializers import (
    AnnualSeriesSerializer,
    FetchRequestSerializer,
    ParameterSerializer,
    RegionSerializer,
    WeatherDatasetSerializer,
    WeatherRecordCompactSerializer,
    WeatherRecordSerializer,
)

logger = logging.getLogger(__name__)


class ParameterViewSet(viewsets.ReadOnlyModelViewSet):
    """List all available climate parameters."""
    queryset = Parameter.objects.all()
    serializer_class = ParameterSerializer
    pagination_class = None


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    """List all available UK regions."""
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    pagination_class = None


class WeatherDatasetViewSet(viewsets.ReadOnlyModelViewSet):
    """List all fetched datasets (parameter × region combinations)."""
    queryset = WeatherDataset.objects.select_related('parameter', 'region').all()
    serializer_class = WeatherDatasetSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['parameter__code', 'region__code']
    pagination_class = None


class WeatherRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Retrieve weather records. Filter by parameter, region, and year range.
    """
    queryset = WeatherRecord.objects.select_related(
        'dataset__parameter', 'dataset__region'
    ).all()
    serializer_class = WeatherRecordSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {
        'dataset__parameter__code': ['exact'],
        'dataset__region__code': ['exact'],
        'year': ['exact', 'gte', 'lte'],
    }
    ordering_fields = ['year']
    ordering = ['year']

    @extend_schema(
        parameters=[
            OpenApiParameter('parameter', str, description='Parameter code e.g. Tmax'),
            OpenApiParameter('region', str, description='Region code e.g. UK'),
            OpenApiParameter('year_from', int, description='Start year (inclusive)'),
            OpenApiParameter('year_to', int, description='End year (inclusive)'),
            OpenApiParameter('format', str, description='"compact" for chart-ready monthly arrays'),
        ]
    )
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())

        # Extra convenience filters
        year_from = request.query_params.get('year_from')
        year_to = request.query_params.get('year_to')
        if year_from:
            qs = qs.filter(year__gte=int(year_from))
        if year_to:
            qs = qs.filter(year__lte=int(year_to))

        fmt = request.query_params.get('format', 'full')

        page = self.paginate_queryset(qs)
        if page is not None:
            Ser = WeatherRecordCompactSerializer if fmt == 'compact' else WeatherRecordSerializer
            return self.get_paginated_response(Ser(page, many=True).data)

        Ser = WeatherRecordCompactSerializer if fmt == 'compact' else WeatherRecordSerializer
        return Response(Ser(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='annual-series')
    @extend_schema(
        parameters=[
            OpenApiParameter('parameter', str, required=True),
            OpenApiParameter('region', str, required=True),
        ],
        description='Return a lightweight annual time-series for charting.'
    )
    def annual_series(self, request):
        """Return year + annual value pairs — optimised for time-series charts."""
        param = request.query_params.get('parameter')
        region = request.query_params.get('region')
        if not param or not region:
            return Response(
                {'error': 'Both "parameter" and "region" query params are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        records = WeatherRecord.objects.filter(
            dataset__parameter__code=param,
            dataset__region__code=region,
        ).order_by('year')

        if not records.exists():
            return Response(
                {'error': f'No data found for {param}/{region}. '
                          f'Use /api/fetch/ to load it first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AnnualSeriesSerializer(records, many=True)
        return Response({
            'parameter': param,
            'region': region,
            'count': records.count(),
            'data': serializer.data,
        })

    @action(detail=False, methods=['get'], url_path='monthly-averages')
    @extend_schema(
        parameters=[
            OpenApiParameter('parameter', str, required=True),
            OpenApiParameter('region', str, required=True),
            OpenApiParameter('year_from', int),
            OpenApiParameter('year_to', int),
        ],
        description='Return average value per calendar month across a year range.'
    )
    def monthly_averages(self, request):
        """Compute mean value for each calendar month across selected years."""
        param = request.query_params.get('parameter')
        region = request.query_params.get('region')
        if not param or not region:
            return Response(
                {'error': 'Both "parameter" and "region" are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = WeatherRecord.objects.filter(
            dataset__parameter__code=param,
            dataset__region__code=region,
        )
        year_from = request.query_params.get('year_from')
        year_to = request.query_params.get('year_to')
        if year_from:
            qs = qs.filter(year__gte=int(year_from))
        if year_to:
            qs = qs.filter(year__lte=int(year_to))

        if not qs.exists():
            return Response({'error': 'No data found.'}, status=status.HTTP_404_NOT_FOUND)

        month_fields = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                        'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        averages = []
        for field, name in zip(month_fields, month_names):
            values = [v for v in qs.values_list(field, flat=True) if v is not None]
            avg = round(sum(values) / len(values), 2) if values else None
            averages.append({'month': name, 'average': avg})

        return Response({
            'parameter': param,
            'region': region,
            'year_range': {
                'from': qs.order_by('year').first().year,
                'to': qs.order_by('year').last().year,
            },
            'monthly_averages': averages,
        })


class FetchDataView(APIView):
    """
    POST to trigger a fresh fetch + ingest of a MetOffice dataset.
    Body: { "parameter": "Tmax", "region": "UK" }
    """

    @extend_schema(
        request=FetchRequestSerializer,
        responses={200: WeatherDatasetSerializer},
        description='Fetch and store a MetOffice climate dataset from source.'
    )
    def post(self, request):
        ser = FetchRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        parameter_code = ser.validated_data['parameter']
        region_code = ser.validated_data['region']

        try:
            url, records = fetch_and_parse(parameter_code, region_code)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        with transaction.atomic():
            param_obj, _ = Parameter.objects.get_or_create(
                code=parameter_code,
                defaults={'display_name': parameter_code, 'unit': ''}
            )
            param_obj.save()  # trigger auto-fill of display_name/unit

            region_obj, _ = Region.objects.get_or_create(
                code=region_code,
                defaults={'display_name': region_code.replace('_', ' ')}
            )

            dataset, _ = WeatherDataset.objects.update_or_create(
                parameter=param_obj,
                region=region_obj,
                defaults={'source_url': url},
            )

            month_fields = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                            'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

            created_count = 0
            for row in records:
                defaults = {f: row.get(f) for f in month_fields}
                defaults['annual'] = row.get('annual')
                _, created = WeatherRecord.objects.update_or_create(
                    dataset=dataset,
                    year=row['year'],
                    defaults=defaults,
                )
                if created:
                    created_count += 1

            dataset.row_count = WeatherRecord.objects.filter(dataset=dataset).count()
            dataset.save()

        logger.info(f"Ingested {dataset.row_count} records for {parameter_code}/{region_code} "
                    f"({created_count} new)")

        return Response({
            'status': 'success',
            'dataset': WeatherDatasetSerializer(dataset).data,
            'records_total': dataset.row_count,
            'records_new': created_count,
        })


class MetaView(APIView):
    """Return available parameters and regions for UI dropdowns."""

    def get(self, request):
        return Response({
            'parameters': VALID_PARAMETERS,
            'regions': VALID_REGIONS,
            'datasets_loaded': WeatherDataset.objects.count(),
        })
