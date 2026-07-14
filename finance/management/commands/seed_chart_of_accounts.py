from django.core.management.base import BaseCommand

from finance.models import Account

DEFAULT_ACCOUNTS = [
    # (code, name, type, is_cash_account)
    ("1000", "Cash", Account.ASSET, True),
    ("1010", "Bank", Account.ASSET, True),
    ("1020", "M-Pesa", Account.ASSET, True),
    ("1030", "Petty Cash", Account.ASSET, True),
    ("1100", "Accounts Receivable", Account.ASSET, False),
    ("1150", "Employee Advances", Account.ASSET, False),
    ("1200", "Inventory", Account.ASSET, False),
    ("1500", "Fixed Assets", Account.ASSET, False),
    ("1510", "Accumulated Depreciation", Account.ASSET, False),
    ("1600", "VAT Receivable (Input VAT)", Account.ASSET, False),
    ("2000", "Accounts Payable", Account.LIABILITY, False),
    ("2100", "VAT Payable (Output VAT)", Account.LIABILITY, False),
    ("2200", "Salaries Payable", Account.LIABILITY, False),
    ("2300", "Payroll Deductions Payable", Account.LIABILITY, False),
    ("3000", "Owner's Equity", Account.EQUITY, False),
    ("3900", "Retained Earnings", Account.EQUITY, False),
    ("4000", "Sales Revenue", Account.INCOME, False),
    ("5000", "Cost of Goods Sold", Account.EXPENSE, False),
    ("5100", "Salaries Expense", Account.EXPENSE, False),
    ("5200", "Rent Expense", Account.EXPENSE, False),
    ("5300", "Utilities Expense", Account.EXPENSE, False),
    ("5400", "Depreciation Expense", Account.EXPENSE, False),
    ("5500", "Vehicle & Repairs Expense", Account.EXPENSE, False),
    ("5600", "Licenses & Permits Expense", Account.EXPENSE, False),
    ("5900", "General Expenses", Account.EXPENSE, False),
]


class Command(BaseCommand):
    help = "Seed the default Chart of Accounts (safe to re-run — skips accounts that already exist by code)."

    def handle(self, *args, **options):
        created = 0
        for code, name, account_type, is_cash in DEFAULT_ACCOUNTS:
            _, was_created = Account.objects.get_or_create(
                code=code, defaults={"name": name, "account_type": account_type, "is_cash_account": is_cash},
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new account(s); {len(DEFAULT_ACCOUNTS) - created} already existed."))
