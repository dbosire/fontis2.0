from django.db import models


class LabTest(models.Model):
    TECHNICIAN_CHOICES = [(t, t) for t in ["Dennis", "Joy", "Rodgers", "Robinson", "Virginia", "Others"]]

    sample_name = models.CharField(max_length=255)
    technician = models.CharField(max_length=255, choices=TECHNICIAN_CHOICES)
    date_created = models.DateTimeField()
    tds = models.DecimalField(max_digits=10, decimal_places=2)
    ec = models.DecimalField(max_digits=10, decimal_places=2)
    ph = models.DecimalField(max_digits=10, decimal_places=2)
    salinity = models.DecimalField(max_digits=10, decimal_places=2)
    temperature = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "lab_test"
        managed = False
        ordering = ["-date_created"]

    def __str__(self):
        return self.sample_name
