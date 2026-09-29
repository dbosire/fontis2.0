from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """The system's audit trail. Populated two ways, both without touching any of
    the ~200 existing view classes: ActivityLogMiddleware (core/middleware.py) logs
    every successful state-changing request (POST/PUT/PATCH/DELETE), and
    core/signals.py hooks Django's own user_logged_in/user_logged_out/
    user_login_failed signals for authentication events."""

    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    ACTION = "action"
    EVENT_CHOICES = [
        (LOGIN, "Login"),
        (LOGOUT, "Logout"),
        (LOGIN_FAILED, "Failed login"),
        (ACTION, "Action"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Snapshot of the username at the time of the event — survives the user being
    # deleted later, and covers failed logins where no user was ever authenticated.
    username = models.CharField(max_length=255, blank=True)
    event_type = models.CharField(max_length=15, choices=EVENT_CHOICES, default=ACTION)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=500, blank=True)
    module = models.CharField(max_length=50, blank=True)
    view_name = models.CharField(max_length=150, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]
        indexes = [
            models.Index(fields=["-date_created"]),
            models.Index(fields=["module"]),
            models.Index(fields=["event_type"]),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.username or 'anonymous'} @ {self.date_created:%Y-%m-%d %H:%M}"
