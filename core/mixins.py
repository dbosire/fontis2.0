from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse


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
        user = self.request.user
        if user.is_superuser:
            return True
        employee = getattr(user, "employee", None)
        if not employee or not employee.role_id:
            return False
        return employee.role.has_permission(self.module_name, self.permission_level)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "You don't have permission to access that section.")
        return redirect(reverse("reports:dashboard"))
