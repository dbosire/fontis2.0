from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    # Phase A: Chart of Accounts + General Ledger
    path("accounts/", views.AccountListView.as_view(), name="accounts"),
    path("accounts/add/", views.AccountCreateView.as_view(), name="account_add"),
    path("accounts/<int:pk>/edit/", views.AccountUpdateView.as_view(), name="account_edit"),
    path("accounts/<int:pk>/delete/", views.AccountDeleteView.as_view(), name="account_delete"),
    path("journal/", views.JournalEntryListView.as_view(), name="journal_entries"),
    path("journal/add/", views.JournalEntryCreateView.as_view(), name="journal_entry_add"),
    path("journal/<int:pk>/void/", views.JournalEntryVoidView.as_view(), name="journal_entry_void"),
    path("trial-balance/", views.TrialBalanceView.as_view(), name="trial_balance"),

    # Phase B: account mapping
    path("settings/mapping/", views.AccountMappingUpdateView.as_view(), name="mapping"),
    path("settings/mapping/category/add/", views.ExpenseCategoryMappingCreateView.as_view(), name="category_mapping_add"),
    path("settings/mapping/category/<int:pk>/delete/", views.ExpenseCategoryMappingDeleteView.as_view(), name="category_mapping_delete"),

    # Phase C: Cashbook, Bank Reconciliation, Petty Cash
    path("cashbook/", views.CashbookView.as_view(), name="cashbook"),
    path("bank-accounts/", views.BankAccountListView.as_view(), name="bank_accounts"),
    path("bank-accounts/add/", views.BankAccountCreateView.as_view(), name="bank_account_add"),
    path("bank-accounts/<int:pk>/statement/", views.BankStatementLineListView.as_view(), name="bank_statement_lines"),
    path("bank-accounts/<int:pk>/reconcile/", views.BankReconciliationView.as_view(), name="bank_reconciliation"),
    path("petty-cash/funds/", views.PettyCashFundListView.as_view(), name="petty_cash_funds"),
    path("petty-cash/funds/add/", views.PettyCashFundCreateView.as_view(), name="petty_cash_fund_add"),
    path("petty-cash/funds/<int:pk>/replenish/", views.PettyCashReplenishView.as_view(), name="petty_cash_replenish"),
    path("petty-cash/vouchers/", views.PettyCashVoucherListView.as_view(), name="petty_cash_vouchers"),
    path("petty-cash/vouchers/add/", views.PettyCashVoucherCreateView.as_view(), name="petty_cash_voucher_add"),

    # Phase D: Accounts Payable + Accounts Receivable
    path("bills/", views.BillListView.as_view(), name="bills"),
    path("bills/add/", views.BillCreateView.as_view(), name="bill_add"),
    path("bills/<int:pk>/", views.BillDetailView.as_view(), name="bill_detail"),
    path("bills/<int:pk>/pay/", views.BillPaymentCreateView.as_view(), name="bill_payment_add"),
    path("bills/<int:pk>/delete/", views.BillDeleteView.as_view(), name="bill_delete"),
    path("ar-aging/", views.ARAgingView.as_view(), name="ar_aging"),

    # Phase E: Budgeting
    path("budgets/", views.BudgetListView.as_view(), name="budgets"),
    path("budgets/add/", views.BudgetCreateView.as_view(), name="budget_add"),
    path("budgets/<int:pk>/", views.BudgetVsActualView.as_view(), name="budget_vs_actual"),

    # Phase F: Fixed Assets + Depreciation
    path("fixed-assets/", views.FixedAssetListView.as_view(), name="fixed_assets"),
    path("fixed-assets/add/", views.FixedAssetCreateView.as_view(), name="fixed_asset_add"),
    path("depreciation/run/", views.RunDepreciationView.as_view(), name="run_depreciation"),

    # Phase G: Tax / VAT
    path("tax-rates/", views.TaxRateListView.as_view(), name="tax_rates"),
    path("tax-rates/add/", views.TaxRateCreateView.as_view(), name="tax_rate_add"),
    path("vat-return/", views.VATReturnView.as_view(), name="vat_return"),

    # Phase H: Financial Statements
    path("income-statement/", views.IncomeStatementView.as_view(), name="income_statement"),
    path("balance-sheet/", views.BalanceSheetView.as_view(), name="balance_sheet"),
]
