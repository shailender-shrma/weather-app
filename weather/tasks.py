"""
Celery tasks for async MetOffice data fetching.

Usage from Django shell:
    from weather.tasks import fetch_dataset_task
    fetch_dataset_task.delay('Tmax', 'UK')
"""
import logging
from celery import shared_task
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_dataset_task(self, parameter_code: str, region_code: str):
    """
    Async task: fetch and ingest a single MetOffice dataset.
    Retries up to 3 times on network failure.
    """
    from .models import Parameter, Region, WeatherDataset, WeatherRecord
    from .parsers import fetch_and_parse

    try:
        url, records = fetch_and_parse(parameter_code, region_code)

        with transaction.atomic():
            param_obj, _ = Parameter.objects.get_or_create(
                code=parameter_code,
                defaults={'display_name': parameter_code, 'unit': ''}
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

        logger.info(f"[Celery] Ingested {dataset.row_count} records for {parameter_code}/{region_code}")
        return {'status': 'success', 'records': dataset.row_count}

    except RuntimeError as exc:
        logger.warning(f"[Celery] Retrying {parameter_code}/{region_code}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def fetch_all_defaults_task():
    """Bulk-fetch default parameters × regions (can be scheduled via Celery Beat)."""
    from .parsers import VALID_PARAMETERS, VALID_REGIONS

    DEFAULT_PARAMETERS = ['Tmax', 'Tmin', 'Tmean', 'Rainfall', 'Sunshine']
    DEFAULT_REGIONS = ['UK', 'England', 'Wales', 'Scotland', 'Northern_Ireland']

    results = []
    for p in DEFAULT_PARAMETERS:
        for r in DEFAULT_REGIONS:
            result = fetch_dataset_task.delay(p, r)
            results.append(result.id)

    return {'dispatched': len(results), 'task_ids': results}
