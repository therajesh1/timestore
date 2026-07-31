from django.core.management.base import BaseCommand

from store.content import BRANDS
from store.models import Brand

HOUSE_BRAND = "The Time Store"


class Command(BaseCommand):
    help = "Seed the retail Brand records shown in the navbar, plus the in-house 'The Time Store' brand."

    def handle(self, *args, **options):
        created_count = 0

        house, created = Brand.objects.get_or_create(
            name=HOUSE_BRAND,
            defaults={"show_in_nav": False, "order": 0},
        )
        if created:
            created_count += 1

        for index, data in enumerate(BRANDS, start=1):
            _, created = Brand.objects.get_or_create(
                name=data["name"],
                defaults={"logo_static": data["image"], "order": index, "show_in_nav": True},
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} new brands ({Brand.objects.count()} total)."))
