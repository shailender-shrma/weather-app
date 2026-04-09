"""
MetOffice climate dataset parser.

Data format (from metoffice.gov.uk/pub/data/weather/uk/climate/datasets/):
  - First few lines are header/metadata (variable text, skip until data rows start)
  - Data rows: Year  Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec  Annual
  - Values of "---" indicate missing data
  - Provisional data may have a trailing '*' on the year
"""
import logging
import re
from typing import Optional
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

METOFFICE_BASE_URL = 'https://www.metoffice.gov.uk/pub/data/weather/uk/climate/datasets'

VALID_PARAMETERS = [
    'Tmax', 'Tmin', 'Tmean', 'Sunshine',
    'Rainfall', 'Raindays1mm', 'AirFrost',
]

VALID_REGIONS = [
    'UK', 'England', 'Wales', 'Scotland', 'Northern_Ireland',
    'England_and_Wales', 'England_N', 'England_S',
    'Scotland_N', 'Scotland_E', 'Scotland_W',
    'EW_E', 'EW_W', 'Midlands', 'East_Anglia',
]


def build_url(parameter: str, region: str) -> str:
    """Build the MetOffice dataset URL for a given parameter and region."""
    return f"{METOFFICE_BASE_URL}/{parameter}/date/{region}.txt"


def fetch_raw_data(url: str) -> Optional[str]:
    """
    Fetch raw text from a MetOffice dataset URL.
    Returns the text content or None on failure.
    """
    try:
        headers = {
            'User-Agent': 'MetOffice-Weather-API/1.0 (educational project)',
            'Accept': 'text/plain',
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error fetching {url}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        return None


def _parse_value(raw: str) -> Optional[float]:
    """
    Convert a raw string cell to float.
    '---' or '---*' → None (missing)
    '12.3*' → 12.3 (provisional, strip asterisk)
    """
    val = raw.strip().rstrip('*').strip()
    if not val or val in ('---', '-'):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def parse_dataset(raw_text: str) -> list[dict]:
    """
    Parse raw MetOffice dataset text into a list of row dicts.

    Returns list of:
        {
          'year': int,
          'jan': float|None, 'feb': float|None, ..., 'dec': float|None,
          'annual': float|None,
          'provisional': bool
        }

    The MetOffice file format:
      - Multiple header lines (skip lines that don't start with a 4-digit year)
      - Data line example:  1884   3.9   4.2   ...  12.3    8.1
    """
    records = []
    lines = raw_text.splitlines()

    month_fields = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                    'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # A data row starts with a 4-digit year (possibly followed by *)
        year_match = re.match(r'^(\d{4})\*?\s+(.+)$', stripped)
        if not year_match:
            continue

        year = int(year_match.group(1))
        provisional = '*' in stripped.split()[0]
        values_raw = year_match.group(2).split()

        # Expect 12 monthly + 1 annual = 13 columns (some datasets may omit annual)
        if len(values_raw) < 12:
            logger.debug(f"Skipping short row for year {year}: {values_raw}")
            continue

        row = {'year': year, 'provisional': provisional}
        for i, field in enumerate(month_fields):
            row[field] = _parse_value(values_raw[i]) if i < len(values_raw) else None

        row['annual'] = _parse_value(values_raw[12]) if len(values_raw) >= 13 else None

        records.append(row)

    return records


def fetch_and_parse(parameter: str, region: str) -> tuple[str, list[dict]]:
    """
    Convenience function: build URL, fetch, parse.

    Returns (url, records) where records is the parsed list.
    Raises ValueError if parameter/region is invalid.
    Raises RuntimeError if fetch fails.
    """
    if parameter not in VALID_PARAMETERS:
        raise ValueError(f"Invalid parameter '{parameter}'. Valid: {VALID_PARAMETERS}")
    if region not in VALID_REGIONS:
        raise ValueError(f"Invalid region '{region}'. Valid: {VALID_REGIONS}")

    url = build_url(parameter, region)
    logger.info(f"Fetching {url}")
    raw = fetch_raw_data(url)
    if raw is None:
        raise RuntimeError(f"Failed to fetch data from {url}")

    records = parse_dataset(raw)
    logger.info(f"Parsed {len(records)} records for {parameter}/{region}")
    return url, records
