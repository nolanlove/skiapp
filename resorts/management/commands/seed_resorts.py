"""
Management command to seed sample resort data.
"""
from django.core.management.base import BaseCommand

from resorts.scraper import seed_sample_resorts


class Command(BaseCommand):
    help = 'Seed the database with sample ski resort data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding resort data...')
        seed_sample_resorts()
        self.stdout.write(self.style.SUCCESS('Successfully seeded resort data!'))

