from .models import CommissionAccount


def compute_commission_for_employee_period(employee, period_start, period_end):
    """Sum of earned_commission() across every CommissionAccount this employee
    manages, restricted to `period_start`..`period_end`. Called from
    employees/views.py::PayrollGenerateView, mirroring how expense_deductions
    is computed inline there today."""
    accounts = CommissionAccount.objects.filter(account_manager=employee)
    return round(sum(acc.earned_commission(period_start, period_end) for acc in accounts), 2)
