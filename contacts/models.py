from django.db import models


class Contact(models.Model):
    # Explicit int PK (not the project-wide BigAutoField default) so FK columns added by
    # new managed=True models (crm.Complaint etc.) match this legacy int(11) column type —
    # see JarType for the same fix and why it's needed (FK creation fails otherwise).
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=150, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contacts"
        managed = False
        ordering = ["name"]

    def __str__(self):
        return self.name
