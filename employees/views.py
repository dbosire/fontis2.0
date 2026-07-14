from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from commissions.services import compute_commission_for_employee_period
from core.mixins import ModulePermissionRequiredMixin
from expenses.models import Expense
from finance.services import sync_journal_for_payroll, void_journal_for_payroll

from .forms import (
    AttendanceForm, DepartmentForm, EmployeeAssetForm, EmployeeForm, LeaveRequestForm,
    PayrollForm, PerformanceReviewForm, RoleForm, RolePermissionFormSet,
    TrainingProgramForm, TrainingRecordForm,
)
from .models import (
    Attendance, Department, Employee, EmployeeAsset, LeaveRequest, Payroll,
    PerformanceReview, Role, TrainingProgram, TrainingRecord,
)


def _today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


def _now():
    # USE_TZ=False project-wide (see fontis/settings/base.py), so MySQL/Django expect
    # naive datetimes only — strip the tzinfo after computing the correct local time.
    return datetime.now(ZoneInfo("Africa/Nairobi")).replace(tzinfo=None)


class ViewEmployeesMixin(ModulePermissionRequiredMixin):
    module_name = "employees"
    permission_level = "view"


class EditEmployeesMixin(ModulePermissionRequiredMixin):
    module_name = "employees"
    permission_level = "edit"


# ---------------------------------------------------------------- Employees / details

class EmployeeListView(ViewEmployeesMixin, ListView):
    model = Employee
    template_name = "employees/employee_list.html"
    context_object_name = "employees"

    def get_queryset(self):
        return Employee.objects.select_related("department", "role")


class EmployeeCreateView(EditEmployeesMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/employee_form.html"
    success_url = reverse_lazy("employees:list")

    def form_valid(self, form):
        messages.success(self.request, "Employee added.")
        return super().form_valid(form)


class EmployeeUpdateView(EditEmployeesMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/employee_form.html"
    success_url = reverse_lazy("employees:list")

    def form_valid(self, form):
        messages.success(self.request, "Employee updated.")
        return super().form_valid(form)


class EmployeeDetailView(ViewEmployeesMixin, View):
    template_name = "employees/employee_detail.html"

    def get(self, request, pk):
        employee = get_object_or_404(Employee.objects.select_related("department", "role"), pk=pk)
        ctx = {
            "employee": employee,
            "assets": employee.assets.all(),
            "attendance_records": employee.attendance_records.all()[:15],
            "leave_requests": employee.leave_requests.all()[:10],
            "payrolls": employee.payrolls.all()[:10],
            "performance_reviews": employee.performance_reviews.all()[:10],
            "training_records": employee.training_records.select_related("program").all(),
            "expenses": employee.expenses.all()[:10],
        }
        return render(request, self.template_name, ctx)


class EmployeeDeleteView(EditEmployeesMixin, DeleteView):
    model = Employee
    success_url = reverse_lazy("employees:list")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:list")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Employee deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Departments

class DepartmentListView(ViewEmployeesMixin, ListView):
    model = Department
    template_name = "employees/department_list.html"
    context_object_name = "departments"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = DepartmentForm()
        return ctx


class DepartmentCreateView(EditEmployeesMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "employees/department_list.html"
    success_url = reverse_lazy("employees:departments")

    def form_valid(self, form):
        messages.success(self.request, "Department saved.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departments"] = Department.objects.all()
        return ctx


class DepartmentDeleteView(EditEmployeesMixin, DeleteView):
    model = Department
    success_url = reverse_lazy("employees:departments")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:departments")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Department deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Roles & permissions

class RoleListView(ViewEmployeesMixin, ListView):
    model = Role
    template_name = "employees/role_list.html"
    context_object_name = "roles"

    def get_queryset(self):
        return Role.objects.prefetch_related("permissions")


class RoleFormView(EditEmployeesMixin, View):
    template_name = "employees/role_form.html"

    def get_object(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(Role, pk=pk) if pk else None

    def get(self, request, *args, **kwargs):
        role = self.get_object()
        form = RoleForm(instance=role)
        formset = RolePermissionFormSet(instance=role)
        return render(request, self.template_name, {"form": form, "formset": formset, "object": role})

    def post(self, request, *args, **kwargs):
        role = self.get_object()
        form = RoleForm(request.POST, instance=role)
        formset = RolePermissionFormSet(request.POST, instance=role)

        if form.is_valid() and formset.is_valid():
            role = form.save()
            formset.instance = role
            formset.save()
            messages.success(request, "Role saved.")
            return redirect(reverse_lazy("employees:roles"))

        return render(request, self.template_name, {"form": form, "formset": formset, "object": role})


class RoleDeleteView(EditEmployeesMixin, DeleteView):
    model = Role
    success_url = reverse_lazy("employees:roles")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:roles")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Role deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Store (assets)

class EmployeeAssetListView(ViewEmployeesMixin, ListView):
    model = EmployeeAsset
    template_name = "employees/asset_list.html"
    context_object_name = "assets"

    def get_queryset(self):
        return EmployeeAsset.objects.select_related("employee")


class EmployeeAssetCreateView(EditEmployeesMixin, CreateView):
    model = EmployeeAsset
    form_class = EmployeeAssetForm
    template_name = "employees/asset_form.html"
    success_url = reverse_lazy("employees:assets")

    def form_valid(self, form):
        messages.success(self.request, "Item issued.")
        return super().form_valid(form)


class EmployeeAssetUpdateView(EditEmployeesMixin, UpdateView):
    model = EmployeeAsset
    form_class = EmployeeAssetForm
    template_name = "employees/asset_form.html"
    success_url = reverse_lazy("employees:assets")

    def form_valid(self, form):
        messages.success(self.request, "Item updated.")
        return super().form_valid(form)


class EmployeeAssetDeleteView(EditEmployeesMixin, DeleteView):
    model = EmployeeAsset
    success_url = reverse_lazy("employees:assets")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:assets")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Item record deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Attendance

class AttendanceListView(ViewEmployeesMixin, ListView):
    model = Attendance
    template_name = "employees/attendance_list.html"
    context_object_name = "records"
    paginate_by = 30

    def get_queryset(self):
        return Attendance.objects.select_related("employee")


class AttendanceCreateView(EditEmployeesMixin, CreateView):
    model = Attendance
    form_class = AttendanceForm
    template_name = "employees/attendance_form.html"
    success_url = reverse_lazy("employees:attendance")

    def form_valid(self, form):
        messages.success(self.request, "Attendance recorded.")
        return super().form_valid(form)

    def form_invalid(self, form):
        if form.errors.get("__all__"):
            messages.error(self.request, "That employee already has an attendance record for that date.")
        return super().form_invalid(form)


class AttendanceDeleteView(EditEmployeesMixin, DeleteView):
    model = Attendance
    success_url = reverse_lazy("employees:attendance")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:attendance")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Attendance record deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Leave

class LeaveRequestListView(ViewEmployeesMixin, ListView):
    model = LeaveRequest
    template_name = "employees/leave_list.html"
    context_object_name = "leave_requests"

    def get_queryset(self):
        return LeaveRequest.objects.select_related("employee")


class LeaveRequestCreateView(EditEmployeesMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = "employees/leave_form.html"
    success_url = reverse_lazy("employees:leave")

    def form_valid(self, form):
        messages.success(self.request, "Leave request submitted.")
        return super().form_valid(form)


class LeaveRequestDecisionView(EditEmployeesMixin, View):
    def post(self, request, pk, decision):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        if decision not in (LeaveRequest.APPROVED, LeaveRequest.REJECTED):
            messages.error(request, "Invalid decision.")
            return redirect(reverse("employees:leave"))

        leave.status = decision
        leave.approved_by = request.user
        leave.date_decided = _now()
        leave.save(update_fields=["status", "approved_by", "date_decided"])
        messages.success(request, f"Leave request {decision}.")
        return redirect(reverse("employees:leave"))


class LeaveRequestDeleteView(EditEmployeesMixin, DeleteView):
    model = LeaveRequest
    success_url = reverse_lazy("employees:leave")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:leave")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Leave request deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Payroll

class PayrollListView(ViewEmployeesMixin, ListView):
    model = Payroll
    template_name = "employees/payroll_list.html"
    context_object_name = "payrolls"

    def get_queryset(self):
        return Payroll.objects.select_related("employee")


class PayrollGenerateView(EditEmployeesMixin, View):
    template_name = "employees/payroll_form.html"

    def get(self, request):
        form = PayrollForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = PayrollForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        payroll = form.save(commit=False)
        # The expense deduction is always computed server-side from the employee's
        # actual Expense records for the period, never trusted from client input.
        payroll.expense_deductions = (
            Expense.objects.filter(
                employee=payroll.employee,
                date_created__date__gte=payroll.period_start,
                date_created__date__lte=payroll.period_end,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        payroll.commission_earned = compute_commission_for_employee_period(
            payroll.employee, payroll.period_start, payroll.period_end
        )
        payroll.save()
        commission_note = (
            f" plus KES {payroll.commission_earned:,.2f} in commission" if payroll.commission_earned else ""
        )
        messages.success(
            request,
            f"Payroll generated for {payroll.employee.get_full_name()}: "
            f"net pay {payroll.net_pay:,.2f} (KES {payroll.expense_deductions:,.2f} deducted for linked expenses{commission_note}).",
        )
        return redirect(reverse("employees:payroll"))


class PayrollStatusView(EditEmployeesMixin, View):
    def post(self, request, pk, status):
        payroll = get_object_or_404(Payroll, pk=pk)
        if status not in (Payroll.FINALIZED, Payroll.PAID):
            messages.error(request, "Invalid status.")
            return redirect(reverse("employees:payroll"))

        was_paid = payroll.status == Payroll.PAID
        payroll.status = status
        if status == Payroll.PAID:
            payroll.paid_date = _today()
            payroll.save(update_fields=["status", "paid_date"])
        else:
            payroll.save(update_fields=["status"])

        if status == Payroll.PAID:
            sync_journal_for_payroll(payroll, user=request.user)
        elif was_paid:
            void_journal_for_payroll(payroll, user=request.user)

        messages.success(request, f"Payroll marked as {payroll.get_status_display()}.")
        return redirect(reverse("employees:payroll"))


class PayrollDeleteView(EditEmployeesMixin, DeleteView):
    model = Payroll
    success_url = reverse_lazy("employees:payroll")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:payroll")
        return ctx

    def form_valid(self, form):
        void_journal_for_payroll(self.object, user=self.request.user)
        return super().form_valid(form)

    def form_valid(self, form):
        messages.success(self.request, "Payroll record deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Performance

class PerformanceReviewListView(ViewEmployeesMixin, ListView):
    model = PerformanceReview
    template_name = "employees/performance_list.html"
    context_object_name = "reviews"

    def get_queryset(self):
        return PerformanceReview.objects.select_related("employee", "reviewer")


class PerformanceReviewCreateView(EditEmployeesMixin, CreateView):
    model = PerformanceReview
    form_class = PerformanceReviewForm
    template_name = "employees/performance_form.html"
    success_url = reverse_lazy("employees:performance")

    def form_valid(self, form):
        form.instance.reviewer = self.request.user
        messages.success(self.request, "Performance review recorded.")
        return super().form_valid(form)


class PerformanceReviewDeleteView(EditEmployeesMixin, DeleteView):
    model = PerformanceReview
    success_url = reverse_lazy("employees:performance")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:performance")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Performance review deleted.")
        return super().form_valid(form)


# ---------------------------------------------------------------- Training

class TrainingProgramListView(ViewEmployeesMixin, ListView):
    model = TrainingProgram
    template_name = "employees/training_program_list.html"
    context_object_name = "programs"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = TrainingProgramForm()
        return ctx


class TrainingProgramCreateView(EditEmployeesMixin, CreateView):
    model = TrainingProgram
    form_class = TrainingProgramForm
    template_name = "employees/training_program_list.html"
    success_url = reverse_lazy("employees:training_programs")

    def form_valid(self, form):
        messages.success(self.request, "Training program saved.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["programs"] = TrainingProgram.objects.all()
        return ctx


class TrainingProgramDeleteView(EditEmployeesMixin, DeleteView):
    model = TrainingProgram
    success_url = reverse_lazy("employees:training_programs")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:training_programs")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Training program deleted.")
        return super().form_valid(form)


class TrainingRecordListView(ViewEmployeesMixin, ListView):
    model = TrainingRecord
    template_name = "employees/training_record_list.html"
    context_object_name = "records"

    def get_queryset(self):
        return TrainingRecord.objects.select_related("employee", "program")


class TrainingRecordCreateView(EditEmployeesMixin, CreateView):
    model = TrainingRecord
    form_class = TrainingRecordForm
    template_name = "employees/training_record_form.html"
    success_url = reverse_lazy("employees:training_records")

    def form_valid(self, form):
        messages.success(self.request, "Training record added.")
        return super().form_valid(form)


class TrainingRecordUpdateView(EditEmployeesMixin, UpdateView):
    model = TrainingRecord
    form_class = TrainingRecordForm
    template_name = "employees/training_record_form.html"
    success_url = reverse_lazy("employees:training_records")

    def form_valid(self, form):
        messages.success(self.request, "Training record updated.")
        return super().form_valid(form)


class TrainingRecordDeleteView(EditEmployeesMixin, DeleteView):
    model = TrainingRecord
    success_url = reverse_lazy("employees:training_records")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("employees:training_records")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Training record deleted.")
        return super().form_valid(form)
