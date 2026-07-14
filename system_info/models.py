from django.db import models


class SystemInfo(models.Model):
    meta_field = models.TextField()
    meta_value = models.TextField()

    class Meta:
        db_table = "system_info"
        managed = False

    def __str__(self):
        return self.meta_field
