from django.core.management.base import BaseCommand

from jobs.seed_data import seed_job_categories


class Command(BaseCommand):
    help = 'Seed FundiConnect job categories and related skills.'

    def handle(self, *args, **options):
        categories, skills = seed_job_categories()
        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded or refreshed {len(categories)} categories and {len(skills)} skills.'
            )
        )
