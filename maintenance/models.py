from django.db import models


class JarType(models.Model):
    ML, LITERS = "ml", "L"
    VOLUME_UNIT_CHOICES = [(ML, "ml"), (LITERS, "L")]

    # jar_types.id is a plain int(11) in the real table, not bigint — must be explicit
    # here since DEFAULT_AUTO_FIELD is BigAutoField, otherwise any real FK pointing at
    # this model (e.g. JarTypeMaterial) gets created with a mismatched column type.
    id = models.AutoField(primary_key=True)
    name = models.TextField()
    description = models.TextField()
    pricing = models.FloatField()
    has_stock = models.CharField(max_length=10, null=True, blank=True)
    stock = models.IntegerField(default=0)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True, null=True)

    # How much water this product actually represents, so sales can be reported in
    # litres sold rather than just jar/bottle counts.
    volume_value = models.FloatField(null=True, blank=True)
    volume_unit = models.CharField(max_length=2, choices=VOLUME_UNIT_CHOICES, default=LITERS)

    class Meta:
        db_table = "jar_types"
        managed = False
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def tracks_stock(self):
        return self.has_stock == "1"

    @property
    def is_inventory_linked(self):
        # material_usages is prefetched as a list in list views; using .all() here
        # reuses that cache instead of issuing a fresh query per row.
        return len(self.material_usages.all()) > 0

    @property
    def linked_material_names(self):
        return ", ".join(usage.material.name for usage in self.material_usages.all())

    @property
    def available_stock(self):
        """The stock number to show/trust for this product. A sale can consume several
        tracked materials at once (e.g. a bottle + a cap + a label); the number of units
        of this product you can actually sell is capped by whichever linked material
        runs out first, so this is the minimum across all of them. Falls back to the
        manually-entered `stock` count for products with no material links at all."""
        usages = list(self.material_usages.all())
        if not usages:
            return self.stock
        return min(
            (usage.material.current_stock / usage.quantity_per_sale) for usage in usages if usage.quantity_per_sale
        )

    @property
    def volume_in_liters(self):
        if self.volume_value is None:
            return 0
        return self.volume_value / 1000 if self.volume_unit == self.ML else self.volume_value


class JarTypeMaterial(models.Model):
    """One raw material consumed when a JarType product is sold, and how much of it.
    A single product can be linked to several materials (e.g. a "New Bottle + Water"
    product consumes a bottle, a cap, and a label all at once)."""

    jar_type = models.ForeignKey(JarType, on_delete=models.CASCADE, related_name="material_usages")
    material = models.ForeignKey(
        "inventory.RawMaterial", on_delete=models.CASCADE, related_name="jar_type_usages"
    )
    quantity_per_sale = models.FloatField(
        default=1, help_text="Units of this material consumed per 1 unit of the product sold."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["jar_type", "material"], name="unique_jar_type_material")
        ]
        ordering = ["material__category", "material__name"]

    def __str__(self):
        return f"{self.jar_type.name} uses {self.quantity_per_sale:g}x {self.material.name}"
