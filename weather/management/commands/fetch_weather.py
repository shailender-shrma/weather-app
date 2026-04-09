"""
Management command to fetch and ingest MetOffice climate datasets.

Usage:
  python manage.py fetch_weather                         # fetch all parameters × regions
  python manage.py fetch_weather --parameter Tmax        # all regions for Tmax
  python manage.py fetch_weather --parameter Tmax --region UK
  python manage.py fetch_weather --parameter Tmax Tmin --region UK England
"""
import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from weather.models import Parameter, Region, WeatherDataset, WeatherRecord
from weather.parsers import (
    VALID_PARAMETERS, VALID_REGIONS, fetch_and_parse
)

logger = logging.getLogger(__name__)

# Default set — core parameters for all major regions
DEFAULT_PARAMETERS = ['Tmax', 'Tmin', 'Tmean', 'Rainfall', 'Sunshine']
DEFAULT_REGIONS = ['UK', 'England', 'Wales', 'Scotland', 'Northern_Ireland']


class Command(BaseCommand):
    help = 'Fetch and ingest MetOffice climate datasets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--parameter', nargs='+', default=None,
            help=f'Parameter codes to fetch. Choices: {VALID_PARAMETERS}',
        )
        parser.add_argument(
            '--region', nargs='+', default=None,
            help=f'Region codes to fetch. Choices: {VALID_REGIONS}',
        )
        parser.add_argument(
            '--all', action='store_true',
            help='Fetch ALL parameter × region combinations (slow!)',
        )

    def handle(self, *args, **options):
        parameters = options['parameter'] or (VALID_PARAMETERS if options['all'] else DEFAULT_PARAMETERS)
        regions = options['region'] or (VALID_REGIONS if options['all'] else DEFAULT_REGIONS)

        # Validate
        for p in parameters:
            if p not in VALID_PARAMETERS:
                raise CommandError(f"Invalid parameter '{p}'. Valid: {VALID_PARAMETERS}")
        for r in regions:
            if r not in VALID_REGIONS:
                raise CommandError(f"Invalid region '{r}'. Valid: {VALID_REGIONS}")

        total = len(parameters) * len(regions)
        self.stdout.write(
            self.style.NOTICE(
                f"Fetching {len(parameters)} parameter(s) × {len(regions)} region(s) = {total} dataset(s)"
            )
        )

        success = 0
        failed = 0

        for param_code in parameters:
            for region_code in regions:
                self.stdout.write(f"  → {param_code} / {region_code} ...", ending=' ')
                try:
                    url, records = fetch_and_parse(param_code, region_code)
                    self._ingest(param_code, region_code, url, records)
                    self.stdout.write(self.style.SUCCESS(f"✓ {len(records)} records"))
                    success += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ {e}"))
                    failed += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nDone. {success} succeeded, {failed} failed.")
        )

    @transaction.atomic
    def _ingest(self, param_code: str, region_code: str, url: str, records: list):
        param_obj, _ = Parameter.objects.get_or_create(
            code=param_code,
            defaults={'display_name': param_code, 'unit': ''}
        )
        param_obj.save()

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
        for row in records:
            defaults = {f: row.get(f) for f in month_fields}
            defaults['annual'] = row.get('annual')
            WeatherRecord.objects.update_or_create(
                dataset=dataset, year=row['year'], defaults=defaults
            )

        dataset.row_count = WeatherRecord.objects.filter(dataset=dataset).count()
        dataset.save()
