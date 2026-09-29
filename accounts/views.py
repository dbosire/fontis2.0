import secrets

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView, UpdateView, FormView

from core.mixins import SuperuserRequiredMixin

from .forms import ProfileForm, SetNewPasswordForm, StyledAuthenticationForm, UserForm
from .models import User


class LoginView(DjangoLoginView):
    template_name = "registration/login.html"
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True


class LogoutView(DjangoLogoutView):
    pass


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated.")
        return super().form_valid(form)


class ChangePasswordView(LoginRequiredMixin, FormView):
    form_class = SetNewPasswordForm
    template_name = "accounts/change_password.html"
    success_url = reverse_lazy("reports:dashboard")

    def form_valid(self, form):
        user = self.request.user
        user.set_password(form.cleaned_data["new_password1"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(self.request, user)
        messages.success(self.request, "Password changed.")
        return super().form_valid(form)


def _generate_temp_password():
    return secrets.token_urlsafe(10)[:10]


def _set_employee_link(user, employee):
    """Applies UserForm's `employee` selection: unlink whoever currently has this
    user's login (if anyone, and if it's changing), then link the newly chosen one.
    A User<->Employee link is one-to-one from the Employee side (Employee.user), so
    this is the only place that relationship actually gets written."""
    from employees.models import Employee

    current = Employee.objects.filter(user=user).first()
    if current and current != employee:
        current.user = None
        current.save(update_fields=["user"])
    if employee and employee.user_id != user.pk:
        employee.user = user
        employee.save(update_fields=["user"])


class UserListView(SuperuserRequiredMixin, ListView):
    """Login accounts — distinct from Employee records (an Employee doesn't need a
    login to exist in the system, and a login doesn't have to be tied to one).
    Superuser-only: creating a login or granting superuser access is a higher-
    privilege action than anything a Role's "edit" permission is meant to cover."""

    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"

    def get_queryset(self):
        qs = User.objects.select_related("employee").order_by("username")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(username__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class UserCreateView(SuperuserRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": UserForm(), "object": None})

    def post(self, request):
        form = UserForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "object": None})

        temp_password = _generate_temp_password()
        user = form.save(commit=False)
        user.set_password(temp_password)
        user.must_change_password = True
        user.save()
        _set_employee_link(user, form.cleaned_data.get("employee"))

        messages.success(
            request,
            f"User \"{user.username}\" created. Temporary password: {temp_password} — "
            "share this with them securely; they'll be required to set their own on first login.",
        )
        return redirect(reverse("accounts:user_list"))


class UserUpdateView(SuperuserRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get_object(self, pk):
        return get_object_or_404(User, pk=pk)

    def get(self, request, pk):
        user = self.get_object(pk)
        return render(request, self.template_name, {"form": UserForm(instance=user), "object": user})

    def post(self, request, pk):
        user = self.get_object(pk)
        form = UserForm(request.POST, instance=user)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "object": user})

        user = form.save()
        _set_employee_link(user, form.cleaned_data.get("employee"))
        messages.success(request, f"User \"{user.username}\" updated.")
        return redirect(reverse("accounts:user_list"))


class UserResetPasswordView(SuperuserRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        temp_password = _generate_temp_password()
        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        messages.success(
            request,
            f"Password reset for \"{user.username}\". Temporary password: {temp_password} — "
            "share this with them securely; they'll be required to set their own on next login.",
        )
        return redirect(reverse("accounts:user_list"))


class UserDeleteView(SuperuserRequiredMixin, DeleteView):
    model = User
    success_url = reverse_lazy("accounts:user_list")
    template_name = "core/components/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse_lazy("accounts:user_list")
        if self.object.pk == self.request.user.pk:
            ctx["extra_warning"] = "This is your own account — deleting it will log you out immediately."
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"User \"{self.object.username}\" deleted.")
        return super().form_valid(form)
