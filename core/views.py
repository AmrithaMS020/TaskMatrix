"""
core/views.py

Stub views matching every route in core/urls.py. Each is a placeholder
that returns a simple HttpResponse so `python manage.py runserver` works
immediately and you can click through the whole route map before any
template or business logic is written. Replace these one workflow at a
time (Company Onboarding first, then Module/Bug lifecycle, then the AI
Risk dashboard hookup).

The Developer views below are fully implemented (not stubs) as the first
real workflow: viewing assigned modules, moving a module through
Pending -> In Progress -> Testing (notifying the Tester), and resolving
bugs logged against a module (reopening it for re-verification).
"""

from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .auth import employee_role_required, global_admin_required, company_admin_required, any_login_required
from .models import Employee, Module, BugReport, Notification, GlobalAdmin, CompanyAdmin, Company, Project
from .services.risk_analyzer import calculate_project_risk, predict_project_delay


def _stub(label):
    return HttpResponse(f"TaskMatrix — {label} (not yet implemented)")


# --- Public / Auth ----------------------------------------------------
def landing_page(request):
    return redirect("core:login")


def company_register(request):
    if request.method != "POST":
        return render(request, "core/company_register.html")

    company_name = request.POST.get("company_name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    address = request.POST.get("address", "").strip()
    admin_name = request.POST.get("admin_name", "").strip()
    admin_username = request.POST.get("admin_username", "").strip()
    admin_password = request.POST.get("admin_password", "")
    admin_password_confirm = request.POST.get("admin_password_confirm", "")

    # Anything the person already typed gets echoed back into the form if
    # validation fails, EXCEPT the two password fields — never re-populate
    # a password field, even the person's own just-typed one.
    repopulate = {
        "company_name": company_name, "email": email, "phone": phone, "address": address,
        "admin_name": admin_name, "admin_username": admin_username,
    }

    if not all([company_name, email, phone, address, admin_name, admin_username, admin_password, admin_password_confirm]):
        messages.error(request, "Please fill in all fields.")
        return render(request, "core/company_register.html", repopulate)

    if admin_password != admin_password_confirm:
        messages.error(request, "Passwords do not match.")
        return render(request, "core/company_register.html", repopulate)

    if len(admin_password) < 8:
        messages.error(request, "Password must be at least 8 characters.")
        return render(request, "core/company_register.html", repopulate)

    if Company.objects.filter(email=email).exists():
        messages.error(request, "A company with this email has already registered.")
        return render(request, "core/company_register.html", repopulate)

    if (CompanyAdmin.objects.filter(username=admin_username).exists()
            or Employee.objects.filter(username=admin_username).exists()
            or GlobalAdmin.objects.filter(username=admin_username).exists()):
        messages.error(request, "That admin username is already taken. Please choose another.")
        return render(request, "core/company_register.html", repopulate)

    company = Company.objects.create(
        company_name=company_name,
        email=email,
        phone=phone,
        address=address,
        status=Company.STATUS_PENDING,
    )

    admin = CompanyAdmin(
        company=company,
        name=admin_name,
        email=email,
        username=admin_username,
    )
    admin.set_password(admin_password)
    admin.save()

    messages.success(
        request,
        f"Thanks, {company_name}! Your registration is pending approval from a Global Admin. "
        "You'll be able to log in with the admin username and password you just set, "
        "once it's approved."
    )
    return redirect("core:login")


def _dashboard_url_for(user_type, role=None):
    """Work out which dashboard to send someone to after logging in."""
    if user_type == "GlobalAdmin":
        return "core:global_admin_dashboard"
    if user_type == "CompanyAdmin":
        return "core:company_admin_dashboard"
    # user_type == "Employee" -> branch further by role
    if role == Employee.ROLE_PM:
        return "core:pm_dashboard"
    if role == Employee.ROLE_DEVELOPER:
        return "core:developer_dashboard"
    if role == Employee.ROLE_TESTER:
        return "core:tester_dashboard"
    return "core:landing"


def unified_login(request):
    if request.method != "POST":
        return render(request, "core/login.html")

    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")

    if not username or not password:
        messages.error(request, "Please enter both username and password.")
        return render(request, "core/login.html")

    # Check each credentialed table in turn. Usernames are unique per table
    # (enforced at the model level), so this order doesn't cause collisions.
    global_admin = GlobalAdmin.objects.filter(username=username).first()
    if global_admin and global_admin.check_password(password):
        request.session.flush()
        request.session["global_admin_id"] = global_admin.global_admin_id
        request.session["user_type"] = "GlobalAdmin"
        request.session["display_name"] = global_admin.name
        messages.success(request, f"Welcome, {global_admin.name}.")
        return redirect(_dashboard_url_for("GlobalAdmin"))

    company_admin = CompanyAdmin.objects.filter(username=username).first()
    if company_admin and company_admin.check_password(password):
        if company_admin.company.status == Company.STATUS_PENDING:
            messages.error(
                request,
                "Your company's registration is still pending approval from a Global Admin. "
                "You'll be able to log in once it's approved."
            )
            return render(request, "core/login.html")
        if company_admin.company.status == Company.STATUS_REJECTED:
            messages.error(
                request,
                "Your company's registration was not approved. Contact TaskMatrix support for details."
            )
            return render(request, "core/login.html")

        request.session.flush()
        request.session["company_admin_id"] = company_admin.company_admin_id
        request.session["user_type"] = "CompanyAdmin"
        request.session["display_name"] = company_admin.name
        messages.success(request, f"Welcome, {company_admin.name}.")
        return redirect(_dashboard_url_for("CompanyAdmin"))

    employee = Employee.objects.filter(username=username).first()
    if employee and employee.check_password(password):
        if employee.status == Employee.STATUS_INACTIVE:
            messages.error(request, "This account has been deactivated. Contact your Company Admin.")
            return render(request, "core/login.html")

        request.session.flush()
        request.session["employee_id"] = employee.employee_id
        request.session["employee_role"] = employee.role
        request.session["user_type"] = "Employee"
        request.session["display_name"] = employee.name
        messages.success(request, f"Welcome, {employee.name}.")
        return redirect(_dashboard_url_for("Employee", role=employee.role))

    messages.error(request, "Invalid username or password.")
    return render(request, "core/login.html")


def logout_view(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect("core:login")



# --- Global Admin -------------------------------------------------------
@global_admin_required
def global_admin_dashboard(request):
    context = {
        "pending_count": Company.objects.filter(status=Company.STATUS_PENDING).count(),
        "approved_count": Company.objects.filter(status=Company.STATUS_APPROVED).count(),
        "rejected_count": Company.objects.filter(status=Company.STATUS_REJECTED).count(),
        "total_companies": Company.objects.count(),
        "total_employees": Employee.objects.count(),
        "total_active_employees": Employee.objects.filter(status=Employee.STATUS_ACTIVE).count(),
        "total_projects": Project.objects.count(),
        "total_projects_in_progress": Project.objects.filter(status=Project.STATUS_IN_PROGRESS).count(),
    }
    return render(request, "core/global_admin_dashboard.html", context)


@global_admin_required
def company_list(request):
    pending_companies = Company.objects.filter(status=Company.STATUS_PENDING).order_by("requested_at")
    decided_companies = (
        Company.objects.exclude(status=Company.STATUS_PENDING)
        .order_by("-decided_at")[:10]
    )
    context = {
        "pending_companies": pending_companies,
        "decided_companies": decided_companies,
    }
    return render(request, "core/company_list.html", context)


@global_admin_required
def company_approve(request, company_id):
    company = get_object_or_404(Company, company_id=company_id)

    if request.method != "POST":
        return redirect("core:company_list")

    if company.status != Company.STATUS_PENDING:
        messages.error(request, f"{company.company_name} has already been decided on.")
        return redirect("core:company_list")

    company.status = Company.STATUS_APPROVED
    company.decided_at = timezone.now()
    company.save(update_fields=["status", "decided_at"])

    # The CompanyAdmin account already exists — it was created at registration
    # time (company_register), with credentials the registrant chose
    # themselves. Approving here just lifts the login block in unified_login,
    # since that checks company.status == Approved before letting them in.
    admin = CompanyAdmin.objects.filter(company=company).first()
    messages.success(
        request,
        f"{company.company_name} has been approved. "
        f"{admin.username if admin else 'Their admin'} can now log in."
    )
    return redirect("core:company_list")


@global_admin_required
def company_reject(request, company_id):
    company = get_object_or_404(Company, company_id=company_id)

    if request.method != "POST":
        return redirect("core:company_list")

    if company.status != Company.STATUS_PENDING:
        messages.error(request, f"{company.company_name} has already been decided on.")
        return redirect("core:company_list")

    company.status = Company.STATUS_REJECTED
    company.decided_at = timezone.now()
    company.save(update_fields=["status", "decided_at"])

    messages.success(request, f"{company.company_name} has been rejected.")
    return redirect("core:company_list")


# --- Company Admin --------------------------------------------------------
@company_admin_required
def company_admin_dashboard(request):
    company_admin = get_object_or_404(CompanyAdmin, company_admin_id=request.session["company_admin_id"])

    projects = Project.objects.filter(company=company_admin.company).order_by("deadline")
    # Attach each project's calculated risk directly onto the object, so the
    # template can loop over one list instead of matching up two separate ones.
    projects_with_risk = []
    high_risk_count = 0
    medium_risk_count = 0
    likely_delayed_count = 0

    for project in projects:
        risk = calculate_project_risk(project)
        delay_pred = predict_project_delay(project)
        project.risk = risk
        project.delay_prediction = delay_pred
        projects_with_risk.append(project)

        if risk["risk_level"] == "High":
            high_risk_count += 1
        elif risk["risk_level"] == "Medium":
            medium_risk_count += 1

        if delay_pred["status"] == "Likely to be Delayed":
            likely_delayed_count += 1

    context = {
        "company_admin": company_admin,
        "employee_count": Employee.objects.filter(company=company_admin.company).count(),
        "active_employee_count": Employee.objects.filter(
            company=company_admin.company, status=Employee.STATUS_ACTIVE
        ).count(),
        "projects": projects_with_risk,
        "high_risk_count": high_risk_count,
        "medium_risk_count": medium_risk_count,
        "likely_delayed_count": likely_delayed_count,
    }
    return render(request, "core/company_admin_dashboard.html", context)


@company_admin_required
def employee_list(request):
    company_admin = get_object_or_404(CompanyAdmin, company_admin_id=request.session["company_admin_id"])
    employees = Employee.objects.filter(company=company_admin.company).order_by("name")
    context = {"employees": employees}
    return render(request, "core/employee_list.html", context)


@company_admin_required
def employee_create(request):
    company_admin = get_object_or_404(CompanyAdmin, company_admin_id=request.session["company_admin_id"])

    if request.method != "POST":
        return render(request, "core/employee_form.html", {"role_choices": Employee.ROLE_CHOICES})

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    role = request.POST.get("role", "")
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")

    repopulate = {
        "name": name, "email": email, "phone": phone, "role": role, "username": username,
        "role_choices": Employee.ROLE_CHOICES,
    }

    if not all([name, email, role, username, password]):
        messages.error(request, "Please fill in all required fields.")
        return render(request, "core/employee_form.html", repopulate)

    if role not in dict(Employee.ROLE_CHOICES):
        messages.error(request, "Please choose a valid role.")
        return render(request, "core/employee_form.html", repopulate)

    if len(password) < 8:
        messages.error(request, "Password must be at least 8 characters.")
        return render(request, "core/employee_form.html", repopulate)

    if (Employee.objects.filter(username=username).exists()
            or CompanyAdmin.objects.filter(username=username).exists()
            or GlobalAdmin.objects.filter(username=username).exists()):
        messages.error(request, "That username is already taken. Please choose another.")
        return render(request, "core/employee_form.html", repopulate)

    if Employee.objects.filter(email=email).exists():
        messages.error(request, "An employee with this email already exists.")
        return render(request, "core/employee_form.html", repopulate)

    employee = Employee(
        company=company_admin.company,
        name=name,
        email=email,
        phone=phone,
        role=role,
        username=username,
        status=Employee.STATUS_ACTIVE,
    )
    employee.set_password(password)
    employee.save()

    messages.success(request, f"{name} has been added as a {role}.")
    return redirect("core:employee_list")


@company_admin_required
def employee_update(request, employee_id):
    company_admin = get_object_or_404(CompanyAdmin, company_admin_id=request.session["company_admin_id"])
    # Scoped to this admin's own company — a Company Admin can never edit
    # another company's employees, even by guessing an employee_id in the URL.
    employee = get_object_or_404(Employee, employee_id=employee_id, company=company_admin.company)

    if request.method != "POST":
        context = {
            "employee": employee,
            "role_choices": Employee.ROLE_CHOICES,
            "name": employee.name, "email": employee.email,
            "phone": employee.phone, "role": employee.role,
        }
        return render(request, "core/employee_form.html", context)

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    role = request.POST.get("role", "")

    repopulate = {
        "employee": employee, "role_choices": Employee.ROLE_CHOICES,
        "name": name, "email": email, "phone": phone, "role": role,
    }

    if not all([name, email, role]):
        messages.error(request, "Please fill in all required fields.")
        return render(request, "core/employee_form.html", repopulate)

    if role not in dict(Employee.ROLE_CHOICES):
        messages.error(request, "Please choose a valid role.")
        return render(request, "core/employee_form.html", repopulate)

    if Employee.objects.filter(email=email).exclude(employee_id=employee.employee_id).exists():
        messages.error(request, "Another employee already uses this email.")
        return render(request, "core/employee_form.html", repopulate)

    employee.name = name
    employee.email = email
    employee.phone = phone
    employee.role = role
    employee.save(update_fields=["name", "email", "phone", "role"])

    messages.success(request, f"{employee.name}'s details have been updated.")
    return redirect("core:employee_list")


@company_admin_required
def employee_deactivate(request, employee_id):
    company_admin = get_object_or_404(CompanyAdmin, company_admin_id=request.session["company_admin_id"])
    employee = get_object_or_404(Employee, employee_id=employee_id, company=company_admin.company)

    if request.method != "POST":
        return redirect("core:employee_list")

    # Toggle: an inactive employee can be reactivated the same way.
    if employee.status == Employee.STATUS_ACTIVE:
        employee.status = Employee.STATUS_INACTIVE
        messages.success(request, f"{employee.name} has been deactivated.")
    else:
        employee.status = Employee.STATUS_ACTIVE
        messages.success(request, f"{employee.name} has been reactivated.")

    employee.save(update_fields=["status"])
    return redirect("core:employee_list")


@company_admin_required
def project_assign(request):
    company_admin = get_object_or_404(CompanyAdmin, company_admin_id=request.session["company_admin_id"])

    project_managers = Employee.objects.filter(
        company=company_admin.company, role=Employee.ROLE_PM, status=Employee.STATUS_ACTIVE
    ).order_by("name")

    if request.method != "POST":
        context = {"project_managers": project_managers, "priority_choices": Project.PRIORITY_CHOICES}
        return render(request, "core/project_assign.html", context)

    client_name = request.POST.get("client_name", "").strip()
    description = request.POST.get("description", "").strip()
    project_manager_id = request.POST.get("project_manager_id", "")
    assign_date = request.POST.get("assign_date", "").strip()
    deadline = request.POST.get("deadline", "").strip()
    priority = request.POST.get("priority", Project.PRIORITY_MEDIUM)

    repopulate = {
        "project_managers": project_managers, "priority_choices": Project.PRIORITY_CHOICES,
        "client_name": client_name, "description": description,
        "project_manager_id": project_manager_id, "assign_date": assign_date,
        "deadline": deadline, "priority": priority,
    }

    if not all([client_name, project_manager_id, assign_date, deadline]):
        messages.error(request, "Please fill in all required fields.")
        return render(request, "core/project_assign.html", repopulate)

    if deadline < assign_date:
        messages.error(request, "Deadline can't be before the assign date.")
        return render(request, "core/project_assign.html", repopulate)

    # Re-validate the chosen PM actually belongs to this admin's own
    # company and is really a Project Manager — guards against a tampered
    # form submission trying to assign someone else's employee.
    pm = project_managers.filter(employee_id=project_manager_id).first()
    if not pm:
        messages.error(request, "Please choose a valid project manager.")
        return render(request, "core/project_assign.html", repopulate)

    if priority not in dict(Project.PRIORITY_CHOICES):
        priority = Project.PRIORITY_MEDIUM

    project = Project.objects.create(
        company=company_admin.company,
        project_manager=pm,
        project_name=client_name,
        description=description,
        start_date=assign_date,
        deadline=deadline,
        priority=priority,
        status=Project.STATUS_NOT_STARTED,
        progress=0,
    )

    Notification.objects.create(
        sender_id=company_admin.company_admin_id,
        sender_role="Company Admin",
        receiver_id=pm.employee_id,
        receiver_role="Employee",
        project=project,
        message=f"You've been assigned a new project: '{client_name}'.",
        notification_type=Notification.TYPE_PROJECT_ASSIGNED,
    )

    messages.success(request, f"Project '{client_name}' has been assigned to {pm.name}.")
    return redirect("core:company_admin_dashboard")


# --- Project Manager --------------------------------------------------------
@employee_role_required(Employee.ROLE_PM)
def pm_dashboard(request):
    pm = get_object_or_404(Employee, employee_id=request.session["employee_id"])

    projects_qs = (
        Project.objects.filter(project_manager=pm)
        .order_by("deadline")
    )

    projects = []
    likely_delayed_count = 0
    for project in projects_qs:
        project.delay_prediction = predict_project_delay(project)
        projects.append(project)
        if project.delay_prediction["status"] == "Likely to be Delayed":
            likely_delayed_count += 1

    unread_notifications = Notification.objects.filter(
        receiver_id=pm.employee_id, receiver_role="Employee", status=Notification.STATUS_UNREAD
    ).order_by("-created_at")

    context = {
        "pm": pm,
        "projects": projects,
        "total_projects": len(projects),
        "in_progress_count": sum(1 for p in projects if p.status == Project.STATUS_IN_PROGRESS),
        "completed_count": sum(1 for p in projects if p.status == Project.STATUS_COMPLETED),
        "likely_delayed_count": likely_delayed_count,
        "unread_notifications": unread_notifications,
    }
    return render(request, "core/pm_dashboard.html", context)


@employee_role_required(Employee.ROLE_PM)
def project_list(request):
    pm = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    projects_qs = Project.objects.filter(project_manager=pm).order_by("deadline")
    projects = []
    for project in projects_qs:
        project.delay_prediction = predict_project_delay(project)
        projects.append(project)
    context = {"pm": pm, "projects": projects}
    return render(request, "core/pm_dashboard.html", context)


@employee_role_required(Employee.ROLE_PM)
def project_create(request):
    pm = get_object_or_404(Employee, employee_id=request.session["employee_id"])

    if request.method != "POST":
        return render(request, "core/project_form.html", {"priority_choices": Project.PRIORITY_CHOICES})

    project_name = request.POST.get("project_name", "").strip()
    description = request.POST.get("description", "").strip()
    start_date = request.POST.get("start_date", "").strip()
    deadline = request.POST.get("deadline", "").strip()
    priority = request.POST.get("priority", "")

    repopulate = {
        "project_name": project_name, "description": description,
        "start_date": start_date, "deadline": deadline, "priority": priority,
        "priority_choices": Project.PRIORITY_CHOICES,
    }

    if not all([project_name, start_date, deadline, priority]):
        messages.error(request, "Please fill in all required fields.")
        return render(request, "core/project_form.html", repopulate)

    if priority not in dict(Project.PRIORITY_CHOICES):
        messages.error(request, "Please choose a valid priority.")
        return render(request, "core/project_form.html", repopulate)

    if deadline < start_date:
        messages.error(request, "Deadline can't be before the start date.")
        return render(request, "core/project_form.html", repopulate)

    project = Project.objects.create(
        company=pm.company,
        project_manager=pm,
        project_name=project_name,
        description=description,
        start_date=start_date,
        deadline=deadline,
        priority=priority,
        status=Project.STATUS_NOT_STARTED,
        progress=0,
    )

    messages.success(request, f"Project '{project_name}' has been created.")
    return redirect("core:project_detail", project_id=project.project_id)


@employee_role_required(Employee.ROLE_PM)
def project_detail(request, project_id):
    pm = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    # Scoped to this PM's own project — a PM can never open another PM's
    # project, even by guessing a project_id in the URL.
    project = get_object_or_404(Project, project_id=project_id, project_manager=pm)

    modules = project.modules.select_related("developer", "tester").order_by("deadline")
    risk = calculate_project_risk(project)
    delay_prediction = predict_project_delay(project)

    context = {
        "project": project,
        "modules": modules,
        "module_count": modules.count(),
        "completed_module_count": modules.filter(status=Module.STATUS_COMPLETED).count(),
        "overdue_module_count": sum(1 for m in modules if m.is_overdue),
        "risk": risk,
        "delay_prediction": delay_prediction,
    }
    return render(request, "core/project_detail.html", context)


def _recalculate_project_progress(project):
    """
    Recompute a project's progress % from its modules' actual completion
    state, instead of leaving it frozen at whatever it was set to when the
    project was created. Also nudges the project's own status forward:
    Not Started -> In Progress once any work exists, and to Completed once
    every module is done.
    """
    total = project.modules.count()
    if total == 0:
        return

    completed = project.modules.filter(status=Module.STATUS_COMPLETED).count()
    new_progress = round((completed / total) * 100)

    project.progress = new_progress
    if new_progress == 100:
        project.status = Project.STATUS_COMPLETED
    elif project.status == Project.STATUS_NOT_STARTED:
        project.status = Project.STATUS_IN_PROGRESS

    project.save(update_fields=["progress", "status"])


@employee_role_required(Employee.ROLE_PM)
def module_create(request, project_id):
    pm = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    project = get_object_or_404(Project, project_id=project_id, project_manager=pm)

    # Only offer this project's own company's active Developers/Testers in
    # the dropdowns — never let a module get assigned to someone from a
    # different company.
    developers = Employee.objects.filter(
        company=project.company, role=Employee.ROLE_DEVELOPER, status=Employee.STATUS_ACTIVE
    ).order_by("name")
    testers = Employee.objects.filter(
        company=project.company, role=Employee.ROLE_TESTER, status=Employee.STATUS_ACTIVE
    ).order_by("name")

    if request.method != "POST":
        context = {"project": project, "developers": developers, "testers": testers}
        return render(request, "core/module_form.html", context)

    module_name = request.POST.get("module_name", "").strip()
    description = request.POST.get("description", "").strip()
    deadline = request.POST.get("deadline", "").strip()
    developer_id = request.POST.get("developer_id", "")
    tester_id = request.POST.get("tester_id", "")

    repopulate = {
        "project": project, "developers": developers, "testers": testers,
        "module_name": module_name, "description": description, "deadline": deadline,
        "developer_id": developer_id, "tester_id": tester_id,
    }

    if not all([module_name, deadline, developer_id, tester_id]):
        messages.error(request, "Please fill in all required fields.")
        return render(request, "core/module_form.html", repopulate)

    if deadline < str(project.start_date):
        messages.error(request, "Module deadline can't be before the project's start date.")
        return render(request, "core/module_form.html", repopulate)

    # Re-validate the chosen developer/tester actually belong to this
    # project's company — guards against a tampered form submission.
    developer = developers.filter(employee_id=developer_id).first()
    tester = testers.filter(employee_id=tester_id).first()
    if not developer or not tester:
        messages.error(request, "Please choose a valid developer and tester.")
        return render(request, "core/module_form.html", repopulate)

    Module.objects.create(
        project=project,
        module_name=module_name,
        description=description,
        developer=developer,
        tester=tester,
        deadline=deadline,
        status=Module.STATUS_PENDING,
    )
    _recalculate_project_progress(project)

    messages.success(request, f"Module '{module_name}' created and assigned to {developer.name}.")
    return redirect("core:project_detail", project_id=project.project_id)


@employee_role_required(Employee.ROLE_PM)
def project_risk_detail(request, project_id):
    pm = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    project = get_object_or_404(Project, project_id=project_id, project_manager=pm)
    risk = calculate_project_risk(project)
    delay_prediction = predict_project_delay(project)

    context = {"project": project, "risk": risk, "delay_prediction": delay_prediction}
    return render(request, "core/project_risk_detail.html", context)


# --- Developer --------------------------------------------------------------

# Status the Developer is allowed to move a module INTO, keyed by its
# CURRENT status. Developers only push work forward as far as "Testing" —
# only a Tester can mark a module "Completed".
_DEV_NEXT_STATUS = {
    Module.STATUS_PENDING: Module.STATUS_IN_PROGRESS,
    Module.STATUS_IN_PROGRESS: Module.STATUS_TESTING,
}


@employee_role_required(Employee.ROLE_DEVELOPER)
def developer_dashboard(request):
    developer = get_object_or_404(Employee, employee_id=request.session["employee_id"])

    modules = (
        Module.objects.filter(developer=developer)
        .exclude(status=Module.STATUS_COMPLETED)
        .select_related("project")
        .order_by("deadline")
    )
    open_bugs = (
        BugReport.objects.filter(developer=developer)
        .exclude(status=BugReport.STATUS_CLOSED)
        .select_related("module")
        .order_by("-severity", "reported_date")
    )

    context = {
        "developer": developer,
        "modules": modules,
        "open_bugs": open_bugs,
        "overdue_count": sum(1 for m in modules if m.is_overdue),
    }
    return render(request, "core/developer_dashboard.html", context)


@employee_role_required(Employee.ROLE_DEVELOPER)
def module_detail_dev(request, module_id):
    developer = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    module = get_object_or_404(Module, module_id=module_id, developer=developer)
    bugs = module.bug_reports.order_by("-reported_date")
    next_status = _DEV_NEXT_STATUS.get(module.status)

    context = {
        "module": module,
        "bugs": bugs,
        "next_status": next_status,
    }
    return render(request, "core/module_detail_dev.html", context)


@employee_role_required(Employee.ROLE_DEVELOPER)
def module_update_status(request, module_id):
    developer = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    module = get_object_or_404(Module, module_id=module_id, developer=developer)

    if request.method != "POST":
        return redirect("core:module_detail_dev", module_id=module.module_id)

    next_status = _DEV_NEXT_STATUS.get(module.status)
    if next_status is None:
        messages.error(request, "This module cannot be advanced further by a Developer.")
        return redirect("core:module_detail_dev", module_id=module.module_id)

    module.status = next_status
    module.save(update_fields=["status"])

    # Moving into "Testing" is the hand-off point: notify the assigned Tester.
    if next_status == Module.STATUS_TESTING and module.tester:
        Notification.objects.create(
            sender_id=developer.employee_id,
            sender_role="Employee",
            receiver_id=module.tester.employee_id,
            receiver_role="Employee",
            project=module.project,
            message=f"Module '{module.module_name}' is ready for testing.",
            notification_type=Notification.TYPE_TASK_COMPLETED,
        )
        messages.success(request, f"Module moved to Testing. {module.tester.name} has been notified.")
    else:
        messages.success(request, f"Module status updated to {next_status}.")

    return redirect("core:module_detail_dev", module_id=module.module_id)


@employee_role_required(Employee.ROLE_DEVELOPER)
def bug_resolve(request, bug_id):
    developer = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    bug = get_object_or_404(BugReport, bug_id=bug_id, developer=developer)

    if request.method != "POST":
        return redirect("core:module_detail_dev", module_id=bug.module.module_id)

    if bug.status == BugReport.STATUS_CLOSED:
        messages.error(request, "This bug is already closed.")
        return redirect("core:module_detail_dev", module_id=bug.module.module_id)

    bug.status = BugReport.STATUS_FIXED
    bug.resolved_date = timezone.now()
    bug.save(update_fields=["status", "resolved_date"])

    # Resubmit the module for re-verification.
    module = bug.module
    module.status = Module.STATUS_TESTING
    module.save(update_fields=["status"])

    if bug.tester:
        Notification.objects.create(
            sender_id=developer.employee_id,
            sender_role="Employee",
            receiver_id=bug.tester.employee_id,
            receiver_role="Employee",
            project=module.project,
            message=f"Bug '{bug.bug_title}' marked fixed on '{module.module_name}' — please re-verify.",
            notification_type=Notification.TYPE_BUG_REPORT,
        )

    messages.success(request, "Bug marked as fixed. Module resubmitted for testing.")
    return redirect("core:module_detail_dev", module_id=module.module_id)



# --- Tester -------------------------------------------------------------
@employee_role_required(Employee.ROLE_TESTER)
def tester_dashboard(request):
    tester = get_object_or_404(Employee, employee_id=request.session["employee_id"])

    # Modules ready to test right now.
    testing_modules = (
        Module.objects.filter(tester=tester, status=Module.STATUS_TESTING)
        .select_related("project", "developer")
        .order_by("deadline")
    )
    # Everything else this tester is attached to, for visibility (not actionable yet).
    other_modules = (
        Module.objects.filter(tester=tester)
        .exclude(status=Module.STATUS_TESTING)
        .exclude(status=Module.STATUS_COMPLETED)
        .select_related("project", "developer")
        .order_by("deadline")
    )
    my_open_bugs = (
        BugReport.objects.filter(tester=tester)
        .exclude(status=BugReport.STATUS_CLOSED)
        .select_related("module")
        .order_by("-severity", "reported_date")
    )

    context = {
        "tester": tester,
        "testing_modules": testing_modules,
        "other_modules": other_modules,
        "my_open_bugs": my_open_bugs,
    }
    return render(request, "core/tester_dashboard.html", context)


@employee_role_required(Employee.ROLE_TESTER)
def module_detail_test(request, module_id):
    tester = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    module = get_object_or_404(Module, module_id=module_id, tester=tester)
    bugs = module.bug_reports.order_by("-reported_date")

    context = {
        "module": module,
        "bugs": bugs,
        "can_verify": module.status == Module.STATUS_TESTING,
    }
    return render(request, "core/module_detail_test.html", context)


@employee_role_required(Employee.ROLE_TESTER)
def module_verify(request, module_id):
    tester = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    module = get_object_or_404(Module, module_id=module_id, tester=tester)

    if request.method != "POST":
        return redirect("core:module_detail_test", module_id=module.module_id)

    if module.status != Module.STATUS_TESTING:
        messages.error(request, "Only modules currently in Testing can be verified.")
        return redirect("core:module_detail_test", module_id=module.module_id)

    module.status = Module.STATUS_COMPLETED
    module.completed_date = timezone.now().date()
    module.save(update_fields=["status", "completed_date"])
    _recalculate_project_progress(module.project)

    # Notify the Project Manager that a module has cleared testing.
    pm = module.project.project_manager
    if pm:
        Notification.objects.create(
            sender_id=tester.employee_id,
            sender_role="Employee",
            receiver_id=pm.employee_id,
            receiver_role="Employee",
            project=module.project,
            message=f"Module '{module.module_name}' passed testing and is now Completed.",
            notification_type=Notification.TYPE_TASK_COMPLETED,
        )

    messages.success(request, f"Module '{module.module_name}' approved and marked Completed.")
    return redirect("core:tester_dashboard")


@employee_role_required(Employee.ROLE_TESTER)
def bug_report_create(request, module_id):
    tester = get_object_or_404(Employee, employee_id=request.session["employee_id"])
    module = get_object_or_404(Module, module_id=module_id, tester=tester)

    if request.method == "POST":
        bug_title = request.POST.get("bug_title", "").strip()
        description = request.POST.get("description", "").strip()
        severity = request.POST.get("severity", BugReport.SEVERITY_MEDIUM)

        if not bug_title:
            messages.error(request, "Bug title is required.")
            return redirect("core:module_detail_test", module_id=module.module_id)

        if severity not in dict(BugReport.SEVERITY_CHOICES):
            severity = BugReport.SEVERITY_MEDIUM

        BugReport.objects.create(
            module=module,
            tester=tester,
            developer=module.developer,
            bug_title=bug_title,
            description=description,
            severity=severity,
            status=BugReport.STATUS_OPEN,
        )

        # Rejected -> module goes back to In Progress, Developer notified.
        module.status = Module.STATUS_IN_PROGRESS
        module.save(update_fields=["status"])

        if module.developer:
            Notification.objects.create(
                sender_id=tester.employee_id,
                sender_role="Employee",
                receiver_id=module.developer.employee_id,
                receiver_role="Employee",
                project=module.project,
                message=f"Bug '{bug_title}' logged on '{module.module_name}' — needs a fix.",
                notification_type=Notification.TYPE_BUG_REPORT,
            )

        messages.success(request, "Bug reported. Module sent back to the developer.")
        return redirect("core:tester_dashboard")

    # GET: show the report-bug form.
    context = {"module": module, "severity_choices": BugReport.SEVERITY_CHOICES}
    return render(request, "core/bug_report_form.html", context)


# --- Notifications (shared) -----------------------------------------------
def _current_person(request):
    """Work out who's logged in right now, regardless of role, so the
    notification inbox can look up 'my' notifications for any account type."""
    if request.session.get("employee_id"):
        return request.session["employee_id"], "Employee"
    if request.session.get("company_admin_id"):
        return request.session["company_admin_id"], "Company Admin"
    if request.session.get("global_admin_id"):
        return request.session["global_admin_id"], "Global Admin"
    return None, None


@any_login_required
def notification_list(request):
    receiver_id, receiver_role = _current_person(request)
    notifications = Notification.objects.filter(
        receiver_id=receiver_id, receiver_role=receiver_role
    ).order_by("-created_at")

    context = {
        "notifications": notifications,
        "unread_count": notifications.filter(status=Notification.STATUS_UNREAD).count(),
    }
    return render(request, "core/notification_list.html", context)


@any_login_required
def notification_mark_read(request, notification_id):
    receiver_id, receiver_role = _current_person(request)
    # Scoped to the logged-in person's own notifications — nobody can mark
    # someone else's notification as read, even by guessing an ID.
    notification = get_object_or_404(
        Notification, notification_id=notification_id,
        receiver_id=receiver_id, receiver_role=receiver_role,
    )

    if request.method == "POST":
        notification.status = Notification.STATUS_READ
        notification.save(update_fields=["status"])

    return redirect("core:notification_list")