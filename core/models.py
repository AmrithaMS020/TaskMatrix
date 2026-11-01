"""
core/models.py

Django model mapping for the TaskMatrix SDS. Every model below is written
to line up 1:1 with the schema you specified: primary key names, foreign
keys, and status/role choice fields all match the SDS field-for-field so
the generated MySQL tables are exactly what your diagrams describe.

Notes on approach:
- Global_Admin, Company_Admin, and Employee each carry their own
  username/password fields per the SDS (this system does NOT use Django's
  built-in auth.User — role separation and the multi-company boundary are
  modeled explicitly instead, which is what the SRS calls for). Passwords
  are hashed with Django's password hashers before saving; never store
  plaintext.
- All primary keys are explicit AutoFields named to match the SDS
  (e.g. `global_admin_id`) rather than Django's default `id`.
- `related_name` is set on every FK so reverse lookups from templates/views
  read naturally (e.g. `company.employees.all()`).
"""

from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


# ---------------------------------------------------------------------------
# Mixin for the three role tables that each carry credentials
# ---------------------------------------------------------------------------
class CredentialMixin(models.Model):
    """Shared helpers for any model that stores username/password itself."""

    class Meta:
        abstract = True

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


# ---------------------------------------------------------------------------
# 1. Global Admin
# ---------------------------------------------------------------------------
class GlobalAdmin(CredentialMixin, models.Model):
    global_admin_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)  # stored hashed

    class Meta:
        db_table = "global_admin"
        verbose_name = "Global Admin"
        verbose_name_plural = "Global Admins"

    def __str__(self):
        return f"{self.name} (Global Admin)"


# ---------------------------------------------------------------------------
# 2. Company
# ---------------------------------------------------------------------------
class Company(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    company_id = models.AutoField(primary_key=True)
    company_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.company_name


# ---------------------------------------------------------------------------
# 3. Company Admin
# ---------------------------------------------------------------------------
class CompanyAdmin(CredentialMixin, models.Model):
    company_admin_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, db_column="company_id",
        related_name="admins"
    )
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)  # stored hashed

    class Meta:
        db_table = "company_admin"
        verbose_name = "Company Admin"
        verbose_name_plural = "Company Admins"

    def __str__(self):
        return f"{self.name} ({self.company.company_name} Admin)"


# ---------------------------------------------------------------------------
# 4. Employee (Project Manager / Developer / Tester)
# ---------------------------------------------------------------------------
class Employee(CredentialMixin, models.Model):
    ROLE_PM = "Project Manager"
    ROLE_DEVELOPER = "Developer"
    ROLE_TESTER = "Tester"
    ROLE_CHOICES = [
        (ROLE_PM, "Project Manager"),
        (ROLE_DEVELOPER, "Developer"),
        (ROLE_TESTER, "Tester"),
    ]

    STATUS_ACTIVE = "Active"
    STATUS_INACTIVE = "Inactive"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    employee_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, db_column="company_id",
        related_name="employees"
    )
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)  # stored hashed
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )

    class Meta:
        db_table = "employee"

    def __str__(self):
        return f"{self.name} ({self.role})"

    # Convenience helpers used by views/templates for role checks
    @property
    def is_project_manager(self):
        return self.role == self.ROLE_PM

    @property
    def is_developer(self):
        return self.role == self.ROLE_DEVELOPER

    @property
    def is_tester(self):
        return self.role == self.ROLE_TESTER


# ---------------------------------------------------------------------------
# 5. Project
# ---------------------------------------------------------------------------
class Project(models.Model):
    PRIORITY_HIGH = "High"
    PRIORITY_MEDIUM = "Medium"
    PRIORITY_LOW = "Low"
    PRIORITY_CHOICES = [
        (PRIORITY_HIGH, "High"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_LOW, "Low"),
    ]

    STATUS_NOT_STARTED = "Not Started"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED = "Completed"
    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, "Not Started"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    project_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, db_column="company_id",
        related_name="projects"
    )
    project_manager = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True,
        db_column="project_manager_id", related_name="managed_projects",
        limit_choices_to={"role": Employee.ROLE_PM},
    )
    project_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    deadline = models.DateField()
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM
    )
    progress = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED
    )

    class Meta:
        db_table = "project"

    def __str__(self):
        return self.project_name


# ---------------------------------------------------------------------------
# 6. Module (Task)
# ---------------------------------------------------------------------------
class Module(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_TESTING = "Testing"
    STATUS_COMPLETED = "Completed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_TESTING, "Testing"),
        (STATUS_COMPLETED, "Completed"),
    ]

    module_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, db_column="project_id",
        related_name="modules"
    )
    module_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    developer = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="developer_id", related_name="assigned_modules",
        limit_choices_to={"role": Employee.ROLE_DEVELOPER},
    )
    tester = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="tester_id", related_name="testing_modules",
        limit_choices_to={"role": Employee.ROLE_TESTER},
    )
    assigned_date = models.DateField(default=timezone.now)
    deadline = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    class Meta:
        db_table = "module"

    def __str__(self):
        return f"{self.module_name} ({self.project.project_name})"

    @property
    def is_overdue(self):
        return (
            self.status != self.STATUS_COMPLETED
            and self.deadline < timezone.now().date()
        )


# ---------------------------------------------------------------------------
# 7. Bug Report
# ---------------------------------------------------------------------------
class BugReport(models.Model):
    SEVERITY_LOW = "Low"
    SEVERITY_MEDIUM = "Medium"
    SEVERITY_HIGH = "High"
    SEVERITY_CRITICAL = "Critical"
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    STATUS_OPEN = "Open"
    STATUS_FIXED = "Fixed"
    STATUS_CLOSED = "Closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_FIXED, "Fixed"),
        (STATUS_CLOSED, "Closed"),
    ]

    bug_id = models.AutoField(primary_key=True)
    module = models.ForeignKey(
        Module, on_delete=models.CASCADE, db_column="module_id",
        related_name="bug_reports"
    )
    tester = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True,
        db_column="tester_id", related_name="reported_bugs",
        limit_choices_to={"role": Employee.ROLE_TESTER},
    )
    developer = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True,
        db_column="developer_id", related_name="assigned_bugs",
        limit_choices_to={"role": Employee.ROLE_DEVELOPER},
    )
    bug_title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    reported_date = models.DateTimeField(default=timezone.now)
    resolved_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bug_report"

    def __str__(self):
        return f"{self.bug_title} [{self.severity}]"


# ---------------------------------------------------------------------------
# 8. Notification
# ---------------------------------------------------------------------------
class Notification(models.Model):
    TYPE_TASK_COMPLETED = "Task Completed"
    TYPE_BUG_REPORT = "Bug Report"
    TYPE_AI_RISK = "AI Risk"
    TYPE_PROJECT_ASSIGNED = "Project Assigned"
    TYPE_CHOICES = [
        (TYPE_TASK_COMPLETED, "Task Completed"),
        (TYPE_BUG_REPORT, "Bug Report"),
        (TYPE_AI_RISK, "AI Risk"),
        (TYPE_PROJECT_ASSIGNED, "Project Assigned"),
    ]

    STATUS_READ = "Read"
    STATUS_UNREAD = "Unread"
    STATUS_CHOICES = [
        (STATUS_READ, "Read"),
        (STATUS_UNREAD, "Unread"),
    ]

    notification_id = models.AutoField(primary_key=True)

    # sender/receiver can be any of the three credentialed roles, so we
    # identify them generically rather than a straight FK to one table.
    sender_id = models.PositiveIntegerField()
    sender_role = models.CharField(
        max_length=20,
        choices=[
            ("Global Admin", "Global Admin"),
            ("Company Admin", "Company Admin"),
            ("Employee", "Employee"),
            ("System", "System"),
        ],
        default="System",
    )
    receiver_id = models.PositiveIntegerField()
    receiver_role = models.CharField(
        max_length=20,
        choices=[
            ("Global Admin", "Global Admin"),
            ("Company Admin", "Company Admin"),
            ("Employee", "Employee"),
        ],
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, db_column="project_id",
        related_name="notifications", null=True, blank=True,
    )
    message = models.CharField(max_length=500)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_UNREAD
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notification"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.notification_type}] {self.message[:40]}"
