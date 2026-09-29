def visible_modules(request):
    """Every module_name the current user can at least VIEW — exposed as a set so
    the sidebar can gate each section/link with `{% if 'sales' in visible_modules %}`,
    mirroring exactly what ModulePermissionRequiredMixin checks server-side (see
    core/mixins.py). Without this, the sidebar showed every module to every logged-in
    user regardless of their Role's permissions — a module a Role was never granted
    access to still appeared in the nav, even though following the link would
    correctly 403 once there.

    Superusers see everything, matching the mixin's own bypass. An Employee/Role-less
    account sees nothing, matching the mixin's fail-closed default."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    if user.is_superuser:
        from employees.models import MODULE_CHOICES

        return {"visible_modules": {module for module, _ in MODULE_CHOICES}}

    employee = getattr(user, "employee", None)
    if not employee or not employee.role_id:
        return {"visible_modules": set()}

    from django.db.models import Q

    modules = employee.role.permissions.filter(Q(can_view=True) | Q(can_edit=True)).values_list(
        "module", flat=True
    )
    return {"visible_modules": set(modules)}
