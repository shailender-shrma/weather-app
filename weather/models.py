from django.db import models


class Parameter(models.Model):
    """
    A climate variable measured by the Met Office.
    e.g. Tmax, Tmin, Tmean, Sunshine, Rainfall
    """
    PARAMETER_CHOICES = [
        ('Tmax', 'Maximum Temperature (°C)'),
        ('Tmin', 'Minimum Temperature (°C)'),
        ('Tmean', 'Mean Temperature (°C)'),
        ('Sunshine', 'Sunshine Duration (hours)'),
        ('Rainfall', 'Rainfall (mm)'),
        ('Raindays1mm', 'Rain Days ≥ 1mm'),
        ('AirFrost', 'Air Frost Days'),
    ]
    code = models.CharField(max_length=20, unique=True, choices=PARAMETER_CHOICES)
    display_name = models.CharField(max_length=100)
    unit = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} ({self.unit})"

    def save(self, *args, **kwargs):
        # Auto-fill display_name / unit from choices if not provided
        mapping = {
            'Tmax': ('Maximum Temperature', '°C'),
            'Tmin': ('Minimum Temperature', '°C'),
            'Tmean': ('Mean Temperature', '°C'),
            'Sunshine': ('Sunshine Duration', 'hours'),
            'Rainfall': ('Rainfall', 'mm'),
            'Raindays1mm': ('Rain Days ≥ 1mm', 'days'),
            'AirFrost': ('Air Frost Days', 'days'),
        }
        if self.code in mapping and not self.display_name:
            self.display_name, self.unit = mapping[self.code]
        super().save(*args, **kwargs)


class Region(models.Model):
    """
    A UK region covered by the Met Office dataset.
    """
    REGION_CHOICES = [
        ('UK', 'United Kingdom'),
        ('England', 'England'),
        ('Wales', 'Wales'),
        ('Scotland', 'Scotland'),
        ('Northern_Ireland', 'Northern Ireland'),
        ('England_and_Wales', 'England and Wales'),
        ('England_N', 'England North'),
        ('England_S', 'England South'),
        ('Scotland_N', 'Scotland North'),
        ('Scotland_E', 'Scotland East'),
        ('Scotland_W', 'Scotland West'),
        ('EW_E', 'England and Wales East'),
        ('EW_W', 'England and Wales West'),
        ('Midlands', 'Midlands'),
        ('East_Anglia', 'East Anglia'),
    ]
    code = models.CharField(max_length=50, unique=True, choices=REGION_CHOICES)
    display_name = models.CharField(max_length=100)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.display_name


class WeatherDataset(models.Model):
    """
    Represents a fetched dataset for a (parameter, region) combination.
    Tracks when data was last synced.
    """
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE, related_name='datasets')
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='datasets')
    last_fetched = models.DateTimeField(auto_now=True)
    source_url = models.URLField(max_length=500)
    row_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('parameter', 'region')
        ordering = ['parameter__code', 'region__code']

    def __str__(self):
        return f"{self.parameter.code} / {self.region.code}"


class WeatherRecord(models.Model):
    """
    A single year's monthly + annual climate observations.
    """
    dataset = models.ForeignKey(WeatherDataset, on_delete=models.CASCADE, related_name='records')
    year = models.PositiveSmallIntegerField()

    # Monthly values — null means data not available for that month/year combo
    jan = models.FloatField(null=True, blank=True)
    feb = models.FloatField(null=True, blank=True)
    mar = models.FloatField(null=True, blank=True)
    apr = models.FloatField(null=True, blank=True)
    may = models.FloatField(null=True, blank=True)
    jun = models.FloatField(null=True, blank=True)
    jul = models.FloatField(null=True, blank=True)
    aug = models.FloatField(null=True, blank=True)
    sep = models.FloatField(null=True, blank=True)
    oct = models.FloatField(null=True, blank=True)
    nov = models.FloatField(null=True, blank=True)
    dec = models.FloatField(null=True, blank=True)
    annual = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('dataset', 'year')
        ordering = ['dataset', 'year']
        indexes = [
            models.Index(fields=['dataset', 'year']),
        ]

    def __str__(self):
        return f"{self.dataset} — {self.year}"

    @property
    def monthly_values(self):
        """Return dict of month -> value for non-null months."""
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        return {m: getattr(self, m) for m in months if getattr(self, m) is not None}

    MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    MONTH_FIELDS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                    'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
