from django.conf import settings
from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    email = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RawMaterial(models.Model):
    CATEGORY_CHOICES = [
        (c, c)
        for c in [
            "Membranes", "Ozone", "UV Lamps", "Chemicals", "Bottle Caps",
            "Labels", "Bottles", "Jars", "Shrink Wrap", "Other",
        ]
    ]
    UNIT_CHOICES = [(u, u) for u in ["pieces", "liters", "kg", "rolls", "meters", "other"]]

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="pieces")
    current_stock = models.FloatField(default=0)
    reorder_level = models.FloatField(default=0)
    default_supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="materials"
    )
    unit_cost = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level


class Purchase(models.Model):
    material = models.ForeignKey(RawMaterial, on_delete=models.PROTECT, related_name="purchases")
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.FloatField()
    unit_cost = models.FloatField(default=0)
    purchase_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchase_date", "-id"]

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost

    def __str__(self):
        return f"{self.material.name} x{self.quantity} ({self.purchase_date})"


class StockMovement(models.Model):
    PURCHASE, SALE, ADJUSTMENT, WASTAGE = "purchase", "sale", "adjustment", "wastage"
    MOVEMENT_CHOICES = [
        (PURCHASE, "Purchase"),
        (SALE, "Sale"),
        (ADJUSTMENT, "Adjustment"),
        (WASTAGE, "Wastage / Expired"),
    ]

    material = models.ForeignKey(RawMaterial, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    quantity = models.FloatField(help_text="Positive = stock in, negative = stock out")
    reference = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created", "-id"]

    def __str__(self):
        return f"{self.material.name} {self.quantity:+g} ({self.movement_type})"
