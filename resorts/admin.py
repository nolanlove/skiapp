from django.contrib import admin
from .models import Resort


@admin.register(Resort)
class ResortAdmin(admin.ModelAdmin):
    list_display = ['name', 'state', 'is_open', 'base_depth', 'trails_open', 'trails_total', 'last_scraped']
    list_filter = ['is_open', 'state']
    search_fields = ['name', 'state', 'region']
    readonly_fields = ['last_scraped', 'created_at']

