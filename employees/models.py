from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# The set of app sections a Role's permissions can be scoped to. Kept as a flat list of
# (value, label) matching the sidebar sections rather than a separate model, since the
# set of modules changes rarely and a hardcoded list keeps permission checks simple.
MODULE_CHOICES = [
    ("sales", "Sales"),
    ("contacts", "Customer Contacts"),
    ("maintenance", "Pricing"),
    ("reports", "Reports"),
    ("expenses", "Expenses"),
    ("debts", "Debts Management"),
    ("mpesa", "M-Pesa"),
    ("water_test", "Lab Test"),
    ("inventory", "Inventory Management"),
    ("employees", "Employee Management"),
    ("crm", "Customer Relationship Management"),
    ("finance", "Finance"),
    ("purchasing", "Purchasing"),
    ("commissions", "Commissions"),
    ("daily_reconciliation", "Daily Reconciliation"),
    ("system_info", "Settings"),
]


class Role(models.Model):
    """A job role within the company. Doubles as the unit of system-access control:
    a role's RolePermission rows say which app sections its employees (if they also
    have a linked login) can view/edit."""

    name = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="roles")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def has_permission(self, module, level="view"):
        perm = self.permissions.filter(module=module).first()
        if not perm:
            return False
        return perm.can_edit if level == "edit" else (perm.can_view or perm.can_edit)


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    module = models.CharField(max_length=30, choices=MODULE_CHOICES)
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["role", "module"], name="unique_role_module")]
        ordering = ["module"]

    def __str__(self):
        return f"{self.role.name} / {self.get_module_display()}"


class Employee(models.Model):
    MALE, FEMALE = "M", "F"
    GENDER_CHOICES = [(MALE, "Male"), (FEMALE, "Female")]

    FULL_TIME, PART_TIME, CONTRACT, CASUAL = "full_time", "part_time", "contract", "casual"
    EMPLOYMENT_TYPE_CHOICES = [
        (FULL_TIME, "Full-time"), (PART_TIME, "Part-time"), (CONTRACT, "Contract"), (CASUAL, "Casual"),
    ]

    ACTIVE, INACTIVE, TERMINATED = "active", "inactive", "terminated"
    STATUS_CHOICES = [(ACTIVE, "Active"), (INACTIVE, "Inactive"), (TERMINATED, "Terminated")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="employee"
    )
    employee_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    id_number = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default=FULL_TIME)
    date_hired = models.DateField()
    date_terminated = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)

    basic_salary = models.FloatField(default=0)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    kra_pin = models.CharField(max_length=20, blank=True)
    nssf_number = models.CharField(max_length=30, blank=True)
    nhif_number = models.CharField(max_length=30, blank=True, verbose_name="SHA/NHIF number")

    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=50, blank=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class EmployeeAsset(models.Model):
    """Equipment/items issued to an employee (uniforms, tools, ID cards, devices) —
    the "Store" tracking under Employee Management."""

    ISSUED, RETURNED, LOST = "issued", "returned", "lost"
    STATUS_CHOICES = [(ISSUED, "Issued"), (RETURNED, "Returned"), (LOST, "Lost/Damaged")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="assets")
    item_name = models.CharField(max_length=150)
    category = models.CharField(max_length=100, blank=True)
    issued_date = models.DateField()
    returned_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ISSUED)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_date"]

    def __str__(self):
        return f"{self.item_name} -> {self.employee.get_full_name()}"


class Attendance(models.Model):
    PRESENT, ABSENT, LATE, HALF_DAY, ON_LEAVE = "present", "absent", "late", "half_day", "on_leave"
    STATUS_CHOICES = [
        (PRESENT, "Present"), (ABSENT, "Absent"), (LATE, "Late"), (HALF_DAY, "Half Day"), (ON_LEAVE, "On Leave"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PRESENT)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "date"], name="unique_employee_attendance_date")]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.date}"


class LeaveRequest(models.Model):
    ANNUAL, SICK, MATERNITY, PATERNITY, COMPASSIONATE, UNPAID, OTHER = (
        "annual", "sick", "maternity", "paternity", "compassionate", "unpaid", "other"
    )
    LEAVE_TYPE_CHOICES = [
        (ANNUAL, "Annual"), (SICK, "Sick"), (MATERNITY, "Maternity"), (PATERNITY, "Paternity"),
        (COMPASSIONATE, "Compassionate"), (UNPAID, "Unpaid"), (OTHER, "Other"),
    ]

    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    date_requested = models.DateTimeField(auto_now_add=True)
    date_decided = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_requested"]

    def __str__(self):
        return f"{self.employee.get_full_name()} {self.leave_type} ({self.start_date} - {self.end_date})"

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1


class Payroll(models.Model):
    DRAFT, FINALIZED, PAID = "draft", "finalized", "paid"
    STATUS_CHOICES = [(DRAFT, "Draft"), (FINALIZED, "Finalized"), (PAID, "Paid")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payrolls")
    period_start = models.DateField()
    period_end = models.DateField()
    basic_salary = models.FloatField(help_text="Snapshot of the employee's basic salary for this period.")
    expense_deductions = models.FloatField(
        default=0, help_text="Auto-computed total of the employee's Expense records within this period."
    )
    other_deductions = models.FloatField(default=0)
    allowances = models.FloatField(default=0)
    commission_earned = models.FloatField(
        default=0, help_text="Auto-computed total of the employee's earned commission within this period."
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    notes = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    paid_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-period_start"]

    def __str__(self):
        return f"{self.employee.get_full_name()} payroll {self.period_start} - {self.period_end}"

    @property
    def net_pay(self):
        return (
            self.basic_salary + self.allowances + self.commission_earned
            - self.expense_deductions - self.other_deductions
        )


class PerformanceReview(models.Model):
    EXCELLENT, GOOD, SATISFACTORY, NEEDS_IMPROVEMENT, POOR = (
        "excellent", "good", "satisfactory", "needs_improvement", "poor"
    )
    RATING_CHOICES = [
        (EXCELLENT, "Excellent"), (GOOD, "Good"), (SATISFACTORY, "Satisfactory"),
        (NEEDS_IMPROVEMENT, "Needs Improvement"), (POOR, "Poor"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="performance_reviews")
    review_period = models.CharField(max_length=100, help_text='e.g. "Q1 2026"')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    rating = models.CharField(max_length=20, choices=RATING_CHOICES)
    comments = models.TextField(blank=True)
    goals = models.TextField(blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.review_period}"


class TrainingProgram(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    provider = models.CharField(max_length=150, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TrainingRecord(models.Model):
    ENROLLED, COMPLETED, FAILED = "enrolled", "completed", "failed"
    STATUS_CHOICES = [(ENROLLED, "Enrolled"), (COMPLETED, "Completed"), (FAILED, "Failed")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="training_records")
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name="records")
    start_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ENROLLED)
    certificate_expiry = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.program.name}"
