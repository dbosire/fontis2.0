from django.conf import settings
from django.db import models


class PurchaseRequest(models.Model):
    DRAFT, PENDING, APPROVED, REJECTED, CANCELLED, CONVERTED = (
        "draft", "pending", "approved", "rejected", "cancelled", "converted"
    )
    STATUS_CHOICES = [
        (DRAFT, "Draft"), (PENDING, "Pending Approval"), (APPROVED, "Approved"),
        (REJECTED, "Rejected"), (CANCELLED, "Cancelled"), (CONVERTED, "Converted to PO"),
    ]

    requested_by = models.ForeignKey(
        "employees.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="purchase_requests"
    )
    department = models.ForeignKey(
        "employees.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="purchase_requests"
    )
    date_requested = models.DateTimeField(auto_now_add=True)
    needed_by_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_decided = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_requested"]

    def __str__(self):
        return f"PR-{self.pk:05d}" if self.pk else "PR (unsaved)"

    @property
    def reference(self):
        return f"PR-{self.pk:05d}"


class PurchaseRequestLine(models.Model):
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey("inventory.RawMaterial", on_delete=models.PROTECT, related_name="+")
    quantity = models.FloatField()
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.quantity:g} x {self.material.name}"


class PurchaseOrder(models.Model):
    DRAFT, SENT, PARTIALLY_RECEIVED, RECEIVED, CLOSED, CANCELLED = (
        "draft", "sent", "partially_received", "received", "closed", "cancelled"
    )
    STATUS_CHOICES = [
        (DRAFT, "Draft"), (SENT, "Sent"), (PARTIALLY_RECEIVED, "Partially Received"),
        (RECEIVED, "Received"), (CLOSED, "Closed"), (CANCELLED, "Cancelled"),
    ]

    supplier = models.ForeignKey("inventory.Supplier", on_delete=models.PROTECT, related_name="purchase_orders")
    related_request = models.ForeignKey(
        PurchaseRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchase_orders"
    )
    order_date = models.DateField()
    expected_delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-order_date", "-id"]

    def __str__(self):
        return f"PO-{self.pk:05d}" if self.pk else "PO (unsaved)"

    @property
    def reference(self):
        return f"PO-{self.pk:05d}"

    @property
    def total_amount(self):
        return round(sum(line.line_total for line in self.lines.all()), 2)

    @property
    def is_fully_received(self):
        lines = list(self.lines.all())
        return bool(lines) and all(line.quantity_received >= line.quantity_ordered for line in lines)


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    material = models.ForeignKey("inventory.RawMaterial", on_delete=models.PROTECT, related_name="+")
    quantity_ordered = models.FloatField()
    unit_price = models.FloatField(default=0)

    def __str__(self):
        return f"{self.quantity_ordered:g} x {self.material.name}"

    @property
    def line_total(self):
        return round(self.quantity_ordered * self.unit_price, 2)

    @property
    def quantity_received(self):
        return sum(gr_line.quantity_received for gr_line in self.receipt_lines.all())

    @property
    def quantity_outstanding(self):
        return round(self.quantity_ordered - self.quantity_received, 2)


class GoodsReceipt(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    receipt_date = models.DateField()
    received_by = models.ForeignKey(
        "employees.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-receipt_date", "-id"]

    def __str__(self):
        return f"GR-{self.pk:05d}" if self.pk else "GR (unsaved)"

    @property
    def reference(self):
        return f"GR-{self.pk:05d}"


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipt_lines")
    quantity_received = models.FloatField()
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.quantity_received:g} x {self.order_line.material.name}"
