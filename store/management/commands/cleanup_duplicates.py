from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from store.models import Product, OrderItem, ProductColor


class Command(BaseCommand):
    help = "Finds and merges duplicate products in the database based on Model Number and Name."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show duplicates without deleting anything",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.stdout.write("Scanning products for duplicates...")

        # Group products
        # 1. By normalized model_number (if non-empty)
        # 2. Or by normalized name (if model_number is empty)
        products = list(Product.objects.all().order_by("id"))
        
        seen_keys = defaultdict(list)
        for p in products:
            model_key = (p.model_number or "").strip().lower()
            if model_key:
                key = f"model:{model_key}"
            else:
                name_key = (p.name or "").strip().lower()
                key = f"name:{name_key}"
            seen_keys[key].append(p)

        duplicate_groups = {k: v for k, v in seen_keys.items() if len(v) > 1}
        
        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS("No duplicate products found in database."))
            return

        self.stdout.write(f"Found {len(duplicate_groups)} duplicate group(s):")
        total_deleted = 0

        with transaction.atomic():
            for key, group in duplicate_groups.items():
                # Pick the primary product: prefer the one with an image or earlier created
                group_sorted = sorted(
                    group,
                    key=lambda p: (
                        1 if (p.image or p.image_url) else 0,
                        -p.id  # earlier IDs preferred if negative
                    ),
                    reverse=True
                )
                primary = group_sorted[0]
                duplicates = group_sorted[1:]

                self.stdout.write(
                    f"\n  Group '{key}': Keeping ID {primary.id} (Ref: {primary.ref}, '{primary.name}')"
                )

                for dup in duplicates:
                    self.stdout.write(f"    - Merging and removing duplicate ID {dup.id} (Ref: {dup.ref})")
                    
                    if not dry_run:
                        # Copy any missing fields from dup to primary
                        fields_to_update = []
                        for field in [
                            "ean_code", "description", "colour", "collection", "movement",
                            "warranty_period", "glass_material", "strap_material", "strap_color",
                            "dial_color", "case_material", "case_size", "features",
                            "image_url", "image_url2", "image_url3", "image_url4"
                        ]:
                            primary_val = getattr(primary, field, "")
                            dup_val = getattr(dup, field, "")
                            if not primary_val and dup_val:
                                setattr(primary, field, dup_val)
                                fields_to_update.append(field)
                                
                        if fields_to_update:
                            primary.save(update_fields=fields_to_update)

                        # Reassign any OrderItems
                        OrderItem.objects.filter(product=dup).update(product=primary)
                        # Reassign any ProductColors
                        ProductColor.objects.filter(product=dup).update(product=primary)

                        # Delete duplicate product
                        dup.delete()
                        total_deleted += 1
                    else:
                        total_deleted += 1

            if dry_run:
                self.stdout.write(self.style.WARNING(f"\n[DRY RUN] Would delete {total_deleted} duplicate product(s)."))
            else:
                self.stdout.write(self.style.SUCCESS(f"\nSuccessfully cleaned up {total_deleted} duplicate product(s)."))
