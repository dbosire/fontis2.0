from django.conf import settings
from django.db import models

from .storage import get_compliance_storage
from .validators import validate_upload


def _file_field(upload_to):
    return models.FileField(
        upload_to=upload_to, storage=get_compliance_storage, validators=[validate_upload], blank=True,
        help_text="PDF, image or Word document, up to 10 MB.",
    )


class ComplianceDocument(models.Model):
    """The register of licences, permits and reference copies a KEBS inspector asks to
    see. `category` drives the readiness checklist (see services.readiness_checklist):
    it looks for a current document of each required category rather than matching on
    free-text titles."""

    PUBLIC_HEALTH, BUSINESS_PERMIT, KEBS_PERMIT, SCHEME = "public_health", "business_permit", "kebs_permit", "scheme"
    STD_EAS_38, STD_EAS_153, STD_EAS_459, OTHER = "std_eas_38", "std_eas_153", "std_eas_459", "other"
    CATEGORY_CHOICES = [
        (PUBLIC_HEALTH, "Public Health Licence (manufacturing premises)"),
        (BUSINESS_PERMIT, "Single Business Permit"),
        (KEBS_PERMIT, "KEBS certification / permit"),
        (SCHEME, "Signed Scheme of Supervision and Control"),
        (STD_EAS_38, "KS EAS 38:2014 — Labelling of Pre-Packaged Foods (copy)"),
        (STD_EAS_153, "KS EAS 153:2018 — Packaged Drinking Water (copy)"),
        (STD_EAS_459, "KS EAS 459 — Code of Hygiene (copy)"),
        (OTHER, "Other"),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    reference_number = models.CharField(max_length=100, blank=True)
    issuing_authority = models.CharField(max_length=150, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, help_text="Leave blank if it does not expire.")
    file = _file_field("documents/%Y/")
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "-expiry_date"]

    def __str__(self):
        return self.title


class Equipment(models.Model):
    """A critical measuring instrument (TDS/pH meter, scale, ...) whose calibration
    KEBS expects to see certified."""

    name = models.CharField(max_length=150)
    serial_number = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True, help_text="Untick once the instrument is retired.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "equipment"

    def __str__(self):
        return f"{self.name} ({self.serial_number})" if self.serial_number else self.name

    @property
    def latest_calibration(self):
        # max() over .all() so a prefetch_related("calibrations") is honoured.
        return max(self.calibrations.all(), key=lambda c: c.calibration_date, default=None)


class Calibration(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="calibrations")
    calibration_date = models.DateField()
    next_due_date = models.DateField()
    certificate_number = models.CharField(max_length=100, blank=True)
    calibrated_by = models.CharField(max_length=150, blank=True, help_text="Calibration laboratory or body.")
    file = _file_field("calibrations/%Y/")
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-calibration_date"]

    def __str__(self):
        return f"{self.equipment.name} — {self.calibration_date}"


class MedicalCertificate(models.Model):
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="medical_certificates")
    certificate_number = models.CharField(max_length=100, blank=True)
    issued_date = models.DateField()
    expiry_date = models.DateField()
    issuing_facility = models.CharField(max_length=150, blank=True)
    file = _file_field("medical/%Y/")
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expiry_date"]

    def __str__(self):
        return f"{self.employee} — medical, expires {self.expiry_date}"


class PersonnelDocument(models.Model):
    """Quality-control personnel's qualifications and evidence of employment."""

    QUALIFICATION, EMPLOYMENT, OTHER = "qualification", "employment", "other"
    TYPE_CHOICES = [
        (QUALIFICATION, "Qualification / certificate"),
        (EMPLOYMENT, "Evidence of employment"),
        (OTHER, "Other"),
    ]

    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="personnel_documents")
    doc_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=QUALIFICATION)
    title = models.CharField(max_length=200)
    institution = models.CharField(max_length=150, blank=True, help_text="Awarding institution or employer.")
    date_obtained = models.DateField(null=True, blank=True)
    file = _file_field("personnel/%Y/")
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee__first_name", "doc_type", "-date_obtained"]

    def __str__(self):
        return f"{self.employee} — {self.title}"


class Procedure(models.Model):
    """A controlled operating procedure, written and kept in the system. Editing an
    approved procedure's text sends it back to draft (it needs re-approval) and the
    previous wording is snapshotted into ProcedureRevision."""

    RECALL, COMPLAINT, PEST, WASTE = "recall", "complaint", "pest_control", "waste"
    HYGIENE, PERSONAL_HYGIENE, QC, CALIBRATION, SUPERVISION, OTHER = (
        "hygiene", "personal_hygiene", "quality_control", "calibration", "supervision", "other",
    )
    CATEGORY_CHOICES = [
        (RECALL, "Product recall"),
        (COMPLAINT, "Customer complaint handling"),
        (PEST, "Pest control"),
        (WASTE, "Waste management"),
        (HYGIENE, "Cleaning, sanitation & hygiene schedule"),
        (PERSONAL_HYGIENE, "Personal hygiene & protective clothing"),
        (QC, "Quality control"),
        (CALIBRATION, "Equipment calibration"),
        (SUPERVISION, "Scheme of supervision and control"),
        (OTHER, "Other"),
    ]
    DRAFT, APPROVED = "draft", "approved"
    STATUS_CHOICES = [(DRAFT, "Draft"), (APPROVED, "Approved")]

    code = models.CharField(max_length=20, unique=True, help_text="e.g. SOP-001")
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=OTHER)
    version = models.CharField(max_length=20, default="1.0")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    content = models.TextField()
    owner = models.CharField(max_length=150, blank=True, help_text="Person responsible for this procedure.")
    effective_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    approved_by = models.CharField(max_length=150, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.title}"


class ProcedureRevision(models.Model):
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE, related_name="revisions")
    version = models.CharField(max_length=20)
    content = models.TextField()
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]


class PremisesRequirement(models.Model):
    """A physical requirement of the premises the system can't verify itself (hand
    wash point, foot bath, ...) — staff confirm it and the date is kept as evidence."""

    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=300)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_met = models.BooleanField(default=False)
    confirmed_on = models.DateField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.description
