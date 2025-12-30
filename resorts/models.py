"""
Models for caching ski resort data.
"""
from django.db import models
from django.utils import timezone


class Resort(models.Model):
    """
    Cached ski resort data scraped from OnTheSnow.
    """
    # Basic info
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    region = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    
    # Location
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    # Conditions
    base_depth = models.IntegerField(null=True, blank=True, help_text="Base snow depth in inches")
    summit_depth = models.IntegerField(null=True, blank=True, help_text="Summit snow depth in inches")
    new_snow_24h = models.IntegerField(null=True, blank=True, help_text="New snow in last 24h (inches)")
    new_snow_48h = models.IntegerField(null=True, blank=True, help_text="New snow in last 48h (inches)")
    
    # Trail/Lift info
    trails_open = models.IntegerField(null=True, blank=True)
    trails_total = models.IntegerField(null=True, blank=True)
    lifts_open = models.IntegerField(null=True, blank=True)
    lifts_total = models.IntegerField(null=True, blank=True)
    acres_open = models.IntegerField(null=True, blank=True)
    
    # Status
    is_open = models.BooleanField(default=False)
    conditions_updated = models.DateTimeField(null=True, blank=True)
    
    # OnTheSnow URL
    url = models.URLField(max_length=500, blank=True)
    
    # Cache management
    last_scraped = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['state']),
            models.Index(fields=['is_open']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def trails_percent_open(self):
        """Calculate percentage of trails open."""
        if self.trails_total and self.trails_total > 0:
            return round((self.trails_open or 0) / self.trails_total * 100)
        return 0
    
    @property
    def lifts_percent_open(self):
        """Calculate percentage of lifts open."""
        if self.lifts_total and self.lifts_total > 0:
            return round((self.lifts_open or 0) / self.lifts_total * 100)
        return 0
    
    def get_conditions_summary(self):
        """Get a brief summary of current conditions."""
        parts = []
        if self.base_depth:
            parts.append(f"{self.base_depth}\" base")
        if self.new_snow_24h:
            parts.append(f"{self.new_snow_24h}\" new")
        if self.trails_open and self.trails_total:
            parts.append(f"{self.trails_open}/{self.trails_total} trails")
        return " | ".join(parts) if parts else "No data"

