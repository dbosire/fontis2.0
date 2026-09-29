from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse


def has_module_permission(user, module, level="view"):
    """Same check ModulePermissionRequiredMixin.test_func() applies at the class
    level, exposed as a plain function for the rare view that needs a DIFFERENT
    permission level for one specific action than the rest of the view covers —
    e.g. a combined list+create view where listing only needs "view" but the POST
    that actually creates something needs "edit" (see
    finance.views.BankStatementLineListView.post(), which is gated at the class
    level for "view" — a view-only role can legitimately see the list and the form
    — but must additionally pass this check before the POST is allowed to save
    anything)."""
    if user.is_superuser:
        return True
    employee = getattr(user, "employee", None)
    if not employee or not employee.role_id:
        return False
    return employee.role.has_permission(module, level)


class StaffRequiredMixin(LoginRequiredMixin):
    """Every authenticated user in this app is an admin today; this exists as the one
    place to add role checks later without touching every view."""


class ModulePermissionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restricts a view to users whose linked Employee record's Role grants access to
    `module_name` (see employees.models.MODULE_CHOICES / Role.has_permission).
    Superusers always pass. A user with no linked Employee, or an Employee with no
    Role, is denied — fails closed rather than silently allowing everyone through.

    Subclass and set `module_name` (and optionally `permission_level = "edit"` for
    views that modify data) rather than using this directly.
    """

    module_name = None
    permission_level = "view"

    def test_func(self):
        return has_module_permission(self.request.user, self.module_name, self.permission_level)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "You don't have permission to access that section.")
        return redirect(reverse("reports:dashboard"))


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restricted further than ModulePermissionRequiredMixin ever goes: no Role can
    grant this, only Django's own is_superuser flag. Reserved for things a
    settings-editor role shouldn't get for free just by having "edit" on a module —
    e.g. System Health's backup download, which is a full copy of every customer's
    data."""

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "Only a superuser can access that.")
        return redirect(reverse("reports:dashboard"))
