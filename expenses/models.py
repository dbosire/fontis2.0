from django.db import models


class ExpenseCategory(models.Model):
    """Staff-managed list of expense categories. `Expense.category` (and the two
    finance-side fields that share the same vocabulary — ExpenseCategoryAccountMapping
    and PettyCashVoucher) stay plain CharFields rather than FKs into this table: those
    rows live in legacy/managed tables predating this model, and a free-text value
    matched against a live, growable list is simpler than a schema migration+backfill
    for what's ultimately just a labelling concern."""

    name = models.CharField(max_length=255, unique=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Expense categories"

    def __str__(self):
        return self.name


class Expense(models.Model):
    # Explicit int PK — see sales.Sale for why (FK from finance.JournalEntry.related_expense).
    id = models.AutoField(primary_key=True)

    UNPAID, CASH, MPESA = 0, 1, 2
    STATUS_CHOICES = [(UNPAID, "Unpaid"), (CASH, "Paid (Cash)"), (MPESA, "Paid (M-Pesa)")]

    expense_name = models.CharField(max_length=255)
    # No choices= here — validated against the live ExpenseCategory list at the form
    # layer instead, so a category added today is usable immediately without a deploy.
    category = models.CharField(max_length=255)
    amount = models.FloatField()
    date_created = models.DateTimeField()
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=UNPAID)

    # Optional: attribute this expense to a specific employee (e.g. a salary advance or
    # a damage/loss charge) so it can be deducted automatically when running payroll.
    employee = models.ForeignKey(
        "employees.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="employee_id",
        related_name="expenses",
    )

    class Meta:
        db_table = "expenses"
        managed = False
        ordering = ["-date_created"]

    def __str__(self):
        return self.expense_name
