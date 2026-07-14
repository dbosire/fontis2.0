from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Phase A: Chart of Accounts + General Ledger core
# ---------------------------------------------------------------------------

class Account(models.Model):
    ASSET, LIABILITY, EQUITY, INCOME, EXPENSE = "asset", "liability", "equity", "income", "expense"
    TYPE_CHOICES = [
        (ASSET, "Asset"), (LIABILITY, "Liability"), (EQUITY, "Equity"),
        (INCOME, "Income"), (EXPENSE, "Expense"),
    ]
    DEBIT_NORMAL_TYPES = {ASSET, EXPENSE}

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    is_cash_account = models.BooleanField(
        default=False, help_text="Flags Cash/Bank/M-Pesa accounts — used to build the Cashbook view."
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def normal_balance(self):
        return "debit" if self.account_type in self.DEBIT_NORMAL_TYPES else "credit"

    def balance_as_of(self, date=None):
        """Signed balance in this account's own normal-balance direction (positive = a
        normal balance, e.g. an Asset account with more debits than credits)."""
        lines = self.lines.filter(entry__status=JournalEntry.POSTED)
        if date is not None:
            lines = lines.filter(entry__date__lte=date)
        totals = lines.aggregate(debit=models.Sum("debit"), credit=models.Sum("credit"))
        debit_total = totals["debit"] or 0
        credit_total = totals["credit"] or 0
        if self.normal_balance == "debit":
            return round(debit_total - credit_total, 2)
        return round(credit_total - debit_total, 2)


class JournalSequence(models.Model):
    """Singleton counter for JournalEntry.reference — see finance/services.py for why
    this isn't derived from .count()/.latest("id") (races under concurrency, breaks
    after any void)."""

    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class JournalEntry(models.Model):
    POSTED, VOID = "posted", "void"
    STATUS_CHOICES = [(POSTED, "Posted"), (VOID, "Void")]

    MANUAL, SALE, EXPENSE, PAYROLL, BILL, BILL_PAYMENT, DEPRECIATION, PETTY_CASH, ADJUSTMENT = (
        "manual", "sale", "expense", "payroll", "bill", "bill_payment", "depreciation", "petty_cash", "adjustment"
    )
    SOURCE_CHOICES = [
        (MANUAL, "Manual"), (SALE, "Sale"), (EXPENSE, "Expense"), (PAYROLL, "Payroll"),
        (BILL, "Bill"), (BILL_PAYMENT, "Bill Payment"), (DEPRECIATION, "Depreciation"),
        (PETTY_CASH, "Petty Cash"), (ADJUSTMENT, "Adjustment"),
    ]

    date = models.DateField()
    reference = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=255)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=MANUAL)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=POSTED)

    # Typed nullable FKs back to the record that caused this entry (not a
    # GenericForeignKey — the source-type set is small and closed, and typed FKs keep
    # real DB-level referential integrity: a deleted Sale can't silently orphan the
    # audit trail the way a GFK's object_id would).
    related_sale = models.ForeignKey(
        "sales.Sale", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries"
    )
    related_expense = models.ForeignKey(
        "expenses.Expense", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries"
    )
    related_payroll = models.ForeignKey(
        "employees.Payroll", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries"
    )
    related_bill = models.ForeignKey(
        "finance.Bill", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries"
    )
    related_petty_cash_voucher = models.ForeignKey(
        "finance.PettyCashVoucher", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries"
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name_plural = "Journal entries"

    def __str__(self):
        return f"{self.reference} — {self.description}"

    @property
    def total_debit(self):
        return round(sum(line.debit for line in self.lines.all()), 2)

    @property
    def total_credit(self):
        return round(sum(line.credit for line in self.lines.all()), 2)


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    debit = models.FloatField(default=0)
    credit = models.FloatField(default=0)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        amount = self.debit or self.credit
        side = "Dr" if self.debit else "Cr"
        return f"{side} {self.account.code} {amount:g}"


# ---------------------------------------------------------------------------
# Phase B: default account mapping
# ---------------------------------------------------------------------------

class AccountMapping(models.Model):
    """Singleton (see get_solo()) mapping business events to default GL accounts, so
    Sales/Expenses/Payroll can auto-post without the user picking accounts every time."""

    cash_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    mpesa_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    accounts_receivable_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    sales_revenue_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    accounts_payable_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    default_expense_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    salaries_expense_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    employee_advances_account = models.ForeignKey(
        Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Asset account for employee-tagged Expenses (salary advances etc.) — recovered via Payroll.",
    )
    payroll_deductions_payable_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    vat_payable_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    vat_receivable_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    def __str__(self):
        return "Finance Account Mapping"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ExpenseCategoryAccountMapping(models.Model):
    # No choices= — see expenses.models.ExpenseCategory for why.
    category = models.CharField(max_length=255, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")

    def __str__(self):
        return f"{self.category} -> {self.account.code}"


# ---------------------------------------------------------------------------
# Phase C: Cashbook (no model — a live view over JournalLine), Bank Reconciliation,
# Petty Cash
# ---------------------------------------------------------------------------

class BankAccount(models.Model):
    name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=50, blank=True)
    gl_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="bank_accounts")

    def __str__(self):
        return self.name


class BankStatementLine(models.Model):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="statement_lines")
    date = models.DateField()
    description = models.CharField(max_length=255)
    amount = models.FloatField(help_text="Positive = deposit, negative = withdrawal.")
    reconciled = models.BooleanField(default=False)
    matched_journal_line = models.ForeignKey(
        JournalLine, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.bank_account.name} {self.date} {self.amount:+g}"


class PettyCashFund(models.Model):
    name = models.CharField(max_length=150)
    custodian = models.ForeignKey("employees.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    gl_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="petty_cash_funds")
    float_amount = models.FloatField(default=0, help_text="The imprest amount this fund should be replenished to.")

    def __str__(self):
        return self.name


class PettyCashVoucher(models.Model):
    fund = models.ForeignKey(PettyCashFund, on_delete=models.CASCADE, related_name="vouchers")
    date = models.DateField()
    description = models.CharField(max_length=255)
    amount = models.FloatField()
    # No choices= — see expenses.models.ExpenseCategory for why.
    category = models.CharField(max_length=255)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.fund.name} — {self.description} ({self.amount:g})"


# ---------------------------------------------------------------------------
# Phase G: Tax / VAT (TaxRate defined before Bill, which references it)
# ---------------------------------------------------------------------------

class TaxRate(models.Model):
    name = models.CharField(max_length=100)
    rate = models.FloatField(help_text="e.g. 0.16 for 16% VAT, 0 for exempt/zero-rated.")
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.rate * 100:g}%)"


# ---------------------------------------------------------------------------
# Phase D: Accounts Payable (AR has no model — see finance/views.py AR aging report,
# which reads directly from sales.Sale)
# ---------------------------------------------------------------------------

class Bill(models.Model):
    UNPAID, PARTIAL, PAID = "unpaid", "partial", "paid"
    STATUS_CHOICES = [(UNPAID, "Unpaid"), (PARTIAL, "Partially Paid"), (PAID, "Paid")]

    supplier = models.ForeignKey("inventory.Supplier", null=True, blank=True, on_delete=models.SET_NULL, related_name="bills")
    related_purchase = models.ForeignKey(
        "inventory.Purchase", null=True, blank=True, on_delete=models.SET_NULL, related_name="bills",
        help_text="Optional — link this bill to a raw material purchase for reference.",
    )
    related_purchase_order = models.ForeignKey(
        "purchasing.PurchaseOrder", null=True, blank=True, on_delete=models.SET_NULL, related_name="bills",
        help_text="Optional — link this bill to a Purchasing-module purchase order (the Invoice step).",
    )
    expense_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="bills",
        help_text="The expense/asset account this bill's cost should be debited to.",
    )
    tax_rate = models.ForeignKey(TaxRate, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    bill_number = models.CharField(max_length=100, blank=True)
    bill_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount = models.FloatField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=UNPAID)
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-bill_date", "-id"]

    def __str__(self):
        return f"Bill {self.bill_number or self.pk} — {self.supplier or 'Unknown supplier'}"

    @property
    def amount_paid(self):
        return round(sum(p.amount for p in self.payments.all()), 2)

    @property
    def balance_due(self):
        return round(self.amount - self.amount_paid, 2)


class BillPayment(models.Model):
    CASH, MPESA, BANK = "cash", "mpesa", "bank"
    METHOD_CHOICES = [(CASH, "Cash"), (MPESA, "M-Pesa"), (BANK, "Bank")]

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="payments")
    amount = models.FloatField()
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=10, choices=METHOD_CHOICES, default=CASH)
    notes = models.CharField(max_length=255, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return f"Payment {self.amount:g} on {self.bill}"


# ---------------------------------------------------------------------------
# Phase E: Budgeting
# ---------------------------------------------------------------------------

class Budget(models.Model):
    name = models.CharField(max_length=150)
    period_start = models.DateField()
    period_end = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-period_start"]

    def __str__(self):
        return self.name


class BudgetLine(models.Model):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="budget_lines")
    budgeted_amount = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["budget", "account"], name="unique_budget_account")]

    def __str__(self):
        return f"{self.budget.name} / {self.account.code}"


# ---------------------------------------------------------------------------
# Phase F: Fixed Assets + Depreciation
# ---------------------------------------------------------------------------

class FixedAsset(models.Model):
    STRAIGHT_LINE = "straight_line"
    METHOD_CHOICES = [(STRAIGHT_LINE, "Straight Line")]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField()
    cost = models.FloatField()
    salvage_value = models.FloatField(default=0)
    useful_life_years = models.PositiveIntegerField()
    depreciation_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=STRAIGHT_LINE)
    asset_gl_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    depreciation_expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    accumulated_depreciation_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    disposed = models.BooleanField(default=False)
    disposal_date = models.DateField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def monthly_depreciation(self):
        months = self.useful_life_years * 12
        if months <= 0:
            return 0
        return round((self.cost - self.salvage_value) / months, 2)

    @property
    def accumulated_depreciation(self):
        return round(sum(e.amount for e in self.depreciation_entries.all()), 2)

    @property
    def book_value(self):
        return round(self.cost - self.accumulated_depreciation, 2)

    @property
    def is_fully_depreciated(self):
        return self.accumulated_depreciation >= (self.cost - self.salvage_value)


class DepreciationEntry(models.Model):
    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name="depreciation_entries")
    period = models.DateField(help_text="First day of the month this entry covers.")
    amount = models.FloatField()
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["asset", "period"], name="unique_asset_period")]
        ordering = ["-period"]

    def __str__(self):
        return f"{self.asset.name} depreciation {self.period:%b %Y} — {self.amount:g}"
