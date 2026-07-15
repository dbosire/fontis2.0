from django.db import models

from maintenance.models import JarType


class Sale(models.Model):
    # Explicit int PK (not the project-wide BigAutoField default) so FK columns added by
    # new managed=True models (finance.JournalEntry.related_sale etc.) match this legacy
    # int(11) column type — see JarType/Contact for the same fix and why it's needed.
    id = models.AutoField(primary_key=True)

    WALK_IN, DELIVERY = 1, 2
    TYPE_CHOICES = [(WALK_IN, "Walk-In"), (DELIVERY, "For Delivery")]

    UNPAID, CASH, MPESA, UNRESOLVED, PARTIAL = 0, 1, 2, 3, 4
    STATUS_CHOICES = [
        (UNPAID, "Unpaid"),
        (CASH, "Paid (Cash)"),
        (MPESA, "Paid (M-Pesa)"),
        (UNRESOLVED, "Unresolved"),
        (PARTIAL, "Partially Paid"),
    ]

    customer_name = models.TextField()
    type = models.SmallIntegerField(choices=TYPE_CHOICES, default=WALK_IN)
    delivery_address = models.TextField(blank=True)
    amount = models.FloatField(default=0)
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=UNPAID)
    comments = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = "sales"
        managed = False
        ordering = ["-date_created"]

    def __str__(self):
        return f"Sale #{self.pk} - {self.customer_name}"

    def recompute_amount(self):
        self.amount = sum(item.total_amount for item in self.items.all())
        return self.amount

    @property
    def amount_paid(self):
        if self.status in (Sale.CASH, Sale.MPESA):
            return self.amount
        return round(sum(p.amount for p in self.debt_payments.all()), 2)

    @property
    def balance_due(self):
        if self.status in (Sale.CASH, Sale.MPESA):
            return 0.0
        return round(self.amount - self.amount_paid, 2)


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, db_column="sales_id", related_name="items")
    jar_type = models.ForeignKey(JarType, on_delete=models.PROTECT, db_column="jar_type_id")
    quantity = models.FloatField()
    price = models.FloatField()
    total_amount = models.FloatField()

    class Meta:
        db_table = "sales_items"
        managed = False

    def __str__(self):
        return f"{self.quantity} x {self.jar_type.name}"

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.price
        super().save(*args, **kwargs)
