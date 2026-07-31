from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from store.models import Brand, Product

PRODUCTS = [
    dict(ref="MK-01-NC", name="Perpetual Noir", tagline="Master Chronograph", category="Wrist Watch", price=2250000,
         img="https://images.unsplash.com/photo-1634595947394-87012e7b12ba?w=600&h=750&fit=crop&auto=format",
         description="A master chronograph in blackened steel, hand-finished across 1,200 hours in our Andheri atelier."),
    dict(ref="MK-02-LG", name="Lumière Grande", tagline="Tourbillon Perpetuel", category="Wrist Watch", price=5850000,
         img="https://images.unsplash.com/photo-1600003014608-c2ccc1570a65?w=600&h=750&fit=crop&auto=format",
         description="Our flagship tourbillon perpetuel, featuring a hand-engraved dial and 380+ proprietary components."),
    dict(ref="MK-03-EQ", name="Équinoxe", tagline="Moonphase Automatique", category="Wrist Watch", price=2780000,
         img="https://images.unsplash.com/photo-1618215649872-6e3143a716ec?w=600&h=750&fit=crop&auto=format",
         description="A moonphase automatic with a hand-guilloché dial, cased in 18k rose gold."),
    dict(ref="MK-04-OD", name="Obsidian Diver", tagline="Professional Diver 500M", category="Wrist Watch", price=1690000,
         img="https://images.unsplash.com/photo-1547996160-81dfa63595aa?w=600&h=750&fit=crop&auto=format",
         description="Rated to 500 metres, built for the depths without compromising the atelier's finish standards."),
    dict(ref="MK-05-RA", name="Rose Aurora", tagline="Ladies Automatique", category="Wrist Watch", price=1950000,
         img="https://images.unsplash.com/photo-1653651460770-73513a4b25a5?w=600&h=750&fit=crop&auto=format",
         description="A slender automatic in rose gold, designed for the woman who masters her own time."),
    dict(ref="MK-06-DR", name="Diamant Rosé", tagline="Diamond Chronograph", category="Wrist Watch", price=3420000,
         img="https://images.unsplash.com/photo-1751437774882-deeea4352018?w=600&h=750&fit=crop&auto=format",
         description="A diamond-set chronograph in rose gold, with a hand-set bezel of 62 brilliant-cut diamonds."),
    dict(ref="MK-07-PD", name="Perle Dorée", tagline="Mesh Bracelet Diamant", category="Wrist Watch", price=2890000,
         img="https://images.unsplash.com/photo-1451290337906-ac938fc89bce?w=600&h=750&fit=crop&auto=format",
         description="A gold mesh bracelet watch with a diamond-set dial, finished entirely by hand."),
    dict(ref="MK-08-EB", name="Étoile Blanche", tagline="Slim Automatique", category="Wrist Watch", price=1850000,
         img="https://images.unsplash.com/photo-1590736969955-71cc94801759?w=600&h=750&fit=crop&auto=format",
         description="An ultra-slim automatic dress watch in polished steel and gold."),
]


class Command(BaseCommand):
    help = "Seed the catalog with the Time Store's launch collection and a dev admin account."

    def handle(self, *args, **options):
        house_brand, _ = Brand.objects.get_or_create(name="The Time Store", defaults={"show_in_nav": False})

        created_count = 0
        for data in PRODUCTS:
            _, created = Product.objects.get_or_create(
                ref=data["ref"],
                defaults=dict(
                    name=data["name"],
                    tagline=data["tagline"],
                    category=data["category"],
                    brand=house_brand,
                    price=data["price"],
                    mrp=(Decimal(data["price"]) * Decimal("1.08")).quantize(Decimal("1")),
                    image_url=data["img"],
                    description=data["description"],
                    stock=5,
                    featured=False,
                ),
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} new products ({Product.objects.count()} total)."))

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@thetimestore.test", "TimeStore@2025")
            self.stdout.write(self.style.SUCCESS("Created dev admin user → username: admin / password: TimeStore@2025"))
        else:
            self.stdout.write("Admin user already exists, skipped.")
