from django.db import models


class SystemInfo(models.Model):
    meta_field = models.TextField()
    meta_value = models.TextField()

    class Meta:
        db_table = "system_info"
        managed = False

    def __str__(self):
        return self.meta_field


class ScheduledTaskRun(models.Model):
    """One row per backup_db invocation — the System Health page's "Daily scheduler"
    check and "Scheduler runs" table both read this. `source` distinguishes a cron
    invocation from a staff member clicking "Back up now": the scheduler check/table
    only cares about cron runs actually happening on schedule, so a manual backup
    (still a real backup, still listed in the Backups table) doesn't mask a stalled
    cron job by making "last run" look recent."""

    CRON, MANUAL = "cron", "manual"
    SOURCE_CHOICES = [(CRON, "Cron"), (MANUAL, "Manual")]

    OK, FAILED = "ok", "failed"
    STATUS_CHOICES = [(OK, "OK"), (FAILED, "Failed")]

    task = models.CharField(max_length=50, default="backup")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=CRON)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    output = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.task} ({self.source}) — {self.status} @ {self.started_at:%Y-%m-%d %H:%M}"
