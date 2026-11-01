from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from core.models import (
    GlobalAdmin, Company, CompanyAdmin, Employee,
    Project, Module, BugReport, Notification
)
from core.services.risk_analyzer import calculate_project_risk, predict_project_delay


class TaskMatrixModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            company_name="Acme Corp",
            email="info@acme.com",
            phone="1234567890",
            address="123 Street",
            status=Company.STATUS_APPROVED
        )
        self.global_admin = GlobalAdmin.objects.create(
            name="Global Admin User",
            email="gadmin@taskmatrix.com",
            username="gadmin"
        )
        self.global_admin.set_password("pass12345")
        self.global_admin.save()

        self.company_admin = CompanyAdmin.objects.create(
            company=self.company,
            name="Acme Admin",
            email="admin@acme.com",
            username="acmeadmin"
        )
        self.company_admin.set_password("pass12345")
        self.company_admin.save()

        self.pm = Employee.objects.create(
            company=self.company,
            name="PM John",
            email="pm@acme.com",
            role=Employee.ROLE_PM,
            username="pmjohn"
        )
        self.pm.set_password("pass12345")
        self.pm.save()

        self.dev = Employee.objects.create(
            company=self.company,
            name="Dev Alice",
            email="dev@acme.com",
            role=Employee.ROLE_DEVELOPER,
            username="devalice"
        )
        self.dev.set_password("pass12345")
        self.dev.save()

        self.tester = Employee.objects.create(
            company=self.company,
            name="Tester Bob",
            email="tester@acme.com",
            role=Employee.ROLE_TESTER,
            username="testerbob"
        )
        self.tester.set_password("pass12345")
        self.tester.save()

    def test_model_str_methods(self):
        self.assertEqual(str(self.global_admin), "Global Admin User (Global Admin)")
        self.assertEqual(str(self.company), "Acme Corp")
        self.assertEqual(str(self.company_admin), "Acme Admin (Acme Corp Admin)")
        self.assertEqual(str(self.pm), "PM John (Project Manager)")

    def test_employee_role_properties(self):
        self.assertTrue(self.pm.is_project_manager)
        self.assertFalse(self.pm.is_developer)
        self.assertFalse(self.pm.is_tester)

        self.assertTrue(self.dev.is_developer)
        self.assertTrue(self.tester.is_tester)

    def test_password_hashing(self):
        self.assertTrue(self.pm.check_password("pass12345"))
        self.assertFalse(self.pm.check_password("wrongpass"))

    def test_module_is_overdue(self):
        today = date.today()
        project = Project.objects.create(
            company=self.company,
            project_manager=self.pm,
            project_name="Overdue Test",
            start_date=today - timedelta(days=10),
            deadline=today + timedelta(days=10),
        )
        overdue_module = Module.objects.create(
            project=project,
            module_name="Old Task",
            developer=self.dev,
            tester=self.tester,
            deadline=today - timedelta(days=1),
            status=Module.STATUS_IN_PROGRESS
        )
        completed_module = Module.objects.create(
            project=project,
            module_name="Done Task",
            developer=self.dev,
            tester=self.tester,
            deadline=today - timedelta(days=1),
            status=Module.STATUS_COMPLETED
        )
        self.assertTrue(overdue_module.is_overdue)
        self.assertFalse(completed_module.is_overdue)


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(
            company_name="TechCorp",
            email="tech@corp.com",
            phone="9998887770",
            address="Tech Park",
            status=Company.STATUS_APPROVED
        )
        self.gadmin = GlobalAdmin.objects.create(
            name="Super Admin",
            email="super@admin.com",
            username="superadmin"
        )
        self.gadmin.set_password("adminpass")
        self.gadmin.save()

        self.cadmin = CompanyAdmin.objects.create(
            company=self.company,
            name="Tech Admin",
            email="admin@tech.com",
            username="techadmin"
        )
        self.cadmin.set_password("techpass")
        self.cadmin.save()

        self.emp = Employee.objects.create(
            company=self.company,
            name="Jane Dev",
            email="jane@tech.com",
            role=Employee.ROLE_DEVELOPER,
            username="janedev"
        )
        self.emp.set_password("devpass123")
        self.emp.save()

    def test_landing_page_redirects_to_login(self):
        response = self.client.get(reverse("core:landing"))
        self.assertRedirects(response, reverse("core:login"))

    def test_company_registration_validation(self):
        # Mismatched passwords
        response = self.client.post(reverse("core:company_register"), {
            "company_name": "NewCo",
            "email": "new@co.com",
            "phone": "1112223333",
            "address": "City",
            "admin_name": "New Admin",
            "admin_username": "newadmin",
            "admin_password": "password123",
            "admin_password_confirm": "password124",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match.")

        # Short password
        response = self.client.post(reverse("core:company_register"), {
            "company_name": "NewCo",
            "email": "new@co.com",
            "phone": "1112223333",
            "address": "City",
            "admin_name": "New Admin",
            "admin_username": "newadmin",
            "admin_password": "123",
            "admin_password_confirm": "123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password must be at least 8 characters.")

        # Successful registration
        response = self.client.post(reverse("core:company_register"), {
            "company_name": "ValidCo",
            "email": "valid@co.com",
            "phone": "1112223333",
            "address": "City",
            "admin_name": "Valid Admin",
            "admin_username": "validadmin",
            "admin_password": "validpassword",
            "admin_password_confirm": "validpassword",
        })
        self.assertRedirects(response, reverse("core:login"))
        self.assertTrue(Company.objects.filter(company_name="ValidCo", status=Company.STATUS_PENDING).exists())

    def test_unified_login_success(self):
        # Global Admin login
        res1 = self.client.post(reverse("core:login"), {"username": "superadmin", "password": "adminpass"})
        self.assertRedirects(res1, reverse("core:global_admin_dashboard"))

        # Company Admin login
        res2 = self.client.post(reverse("core:login"), {"username": "techadmin", "password": "techpass"})
        self.assertRedirects(res2, reverse("core:company_admin_dashboard"))

        # Employee login
        res3 = self.client.post(reverse("core:login"), {"username": "janedev", "password": "devpass123"})
        self.assertRedirects(res3, reverse("core:developer_dashboard"))

    def test_unified_login_pending_company_admin(self):
        pending_company = Company.objects.create(
            company_name="PendingCo",
            email="p@co.com",
            phone="000",
            address="Addr",
            status=Company.STATUS_PENDING
        )
        padmin = CompanyAdmin.objects.create(
            company=pending_company,
            name="Pending Admin",
            email="padmin@co.com",
            username="padmin"
        )
        padmin.set_password("pass12345")
        padmin.save()

        response = self.client.post(reverse("core:login"), {"username": "padmin", "password": "pass12345"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pending approval")

    def test_logout(self):
        self.client.post(reverse("core:login"), {"username": "superadmin", "password": "adminpass"})
        response = self.client.get(reverse("core:logout"))
        self.assertRedirects(response, reverse("core:login"))
        self.assertNotIn("global_admin_id", self.client.session)


class GlobalAdminWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.gadmin = GlobalAdmin.objects.create(
            name="Global Chief",
            email="chief@taskmatrix.com",
            username="chief"
        )
        self.gadmin.set_password("chiefpass")
        self.gadmin.save()

        self.pending_co = Company.objects.create(
            company_name="Pending Inc",
            email="pending@inc.com",
            phone="123",
            address="Addr",
            status=Company.STATUS_PENDING
        )
        self.client.post(reverse("core:login"), {"username": "chief", "password": "chiefpass"})

    def test_global_admin_dashboard(self):
        response = self.client.get(reverse("core:global_admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Global Admin Dashboard")
        self.assertContains(response, "Pending Companies")

    def test_company_list_displays_pending_companies(self):
        response = self.client.get(reverse("core:company_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending Inc")

    def test_company_approve(self):
        response = self.client.post(reverse("core:company_approve", kwargs={"company_id": self.pending_co.company_id}))
        self.assertRedirects(response, reverse("core:company_list"))
        self.pending_co.refresh_from_db()
        self.assertEqual(self.pending_co.status, Company.STATUS_APPROVED)

    def test_company_reject(self):
        response = self.client.post(reverse("core:company_reject", kwargs={"company_id": self.pending_co.company_id}))
        self.assertRedirects(response, reverse("core:company_list"))
        self.pending_co.refresh_from_db()
        self.assertEqual(self.pending_co.status, Company.STATUS_REJECTED)


class MultiTenancyAndWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(
            company_name="Nexus",
            email="nexus@nexus.com",
            phone="12345",
            address="Nexus Tower",
            status=Company.STATUS_APPROVED
        )
        self.cadmin = CompanyAdmin.objects.create(
            company=self.company,
            name="Nexus Admin",
            email="admin@nexus.com",
            username="nexusadmin"
        )
        self.cadmin.set_password("pass12345")
        self.cadmin.save()

        self.pm = Employee.objects.create(
            company=self.company,
            name="PM Mark",
            email="pm@nexus.com",
            role=Employee.ROLE_PM,
            username="pmmark"
        )
        self.pm.set_password("pass12345")
        self.pm.save()

        self.dev = Employee.objects.create(
            company=self.company,
            name="Dev Dave",
            email="dev@nexus.com",
            role=Employee.ROLE_DEVELOPER,
            username="devdave"
        )
        self.dev.set_password("pass12345")
        self.dev.save()

        self.tester = Employee.objects.create(
            company=self.company,
            name="Tester Tina",
            email="tester@nexus.com",
            role=Employee.ROLE_TESTER,
            username="testertina"
        )
        self.tester.set_password("pass12345")
        self.tester.save()

    def test_complete_project_module_bug_lifecycle(self):
        # 1. Company Admin assigns project to PM
        self.client.post(reverse("core:login"), {"username": "nexusadmin", "password": "pass12345"})
        today = date.today()
        res_proj = self.client.post(reverse("core:project_assign"), {
            "client_name": "Nexus Portal",
            "description": "Portal for Nexus clients",
            "project_manager_id": self.pm.employee_id,
            "assign_date": str(today),
            "deadline": str(today + timedelta(days=30)),
            "priority": Project.PRIORITY_HIGH
        })
        self.assertRedirects(res_proj, reverse("core:company_admin_dashboard"))
        project = Project.objects.get(project_name="Nexus Portal")
        self.assertEqual(project.project_manager, self.pm)

        # 2. PM logs in and creates a module
        self.client.post(reverse("core:login"), {"username": "pmmark", "password": "pass12345"})
        res_mod = self.client.post(reverse("core:module_create", kwargs={"project_id": project.project_id}), {
            "module_name": "User Auth Module",
            "description": "Build user auth",
            "deadline": str(today + timedelta(days=15)),
            "developer_id": self.dev.employee_id,
            "tester_id": self.tester.employee_id,
        })
        self.assertRedirects(res_mod, reverse("core:project_detail", kwargs={"project_id": project.project_id}))
        module = Module.objects.get(module_name="User Auth Module")
        self.assertEqual(module.status, Module.STATUS_PENDING)

        # 3. Developer advances status: Pending -> In Progress -> Testing
        self.client.post(reverse("core:login"), {"username": "devdave", "password": "pass12345"})
        self.client.post(reverse("core:module_update_status", kwargs={"module_id": module.module_id}))
        module.refresh_from_db()
        self.assertEqual(module.status, Module.STATUS_IN_PROGRESS)

        self.client.post(reverse("core:module_update_status", kwargs={"module_id": module.module_id}))
        module.refresh_from_db()
        self.assertEqual(module.status, Module.STATUS_TESTING)

        # Verification: Tester should have received a notification
        self.assertTrue(Notification.objects.filter(
            receiver_id=self.tester.employee_id,
            notification_type=Notification.TYPE_TASK_COMPLETED
        ).exists())

        # 4. Tester logs in, rejects module by creating a bug report
        self.client.post(reverse("core:login"), {"username": "testertina", "password": "pass12345"})
        res_bug = self.client.post(reverse("core:bug_report_create", kwargs={"module_id": module.module_id}), {
            "bug_title": "Login crash on special chars",
            "description": "Entering !@# causes 500 error",
            "severity": BugReport.SEVERITY_HIGH
        })
        self.assertRedirects(res_bug, reverse("core:tester_dashboard"))
        module.refresh_from_db()
        self.assertEqual(module.status, Module.STATUS_IN_PROGRESS)
        bug = BugReport.objects.get(bug_title="Login crash on special chars")
        self.assertEqual(bug.status, BugReport.STATUS_OPEN)

        # 5. Developer fixes bug
        self.client.post(reverse("core:login"), {"username": "devdave", "password": "pass12345"})
        self.client.post(reverse("core:bug_resolve", kwargs={"bug_id": bug.bug_id}))
        bug.refresh_from_db()
        module.refresh_from_db()
        self.assertEqual(bug.status, BugReport.STATUS_FIXED)
        self.assertEqual(module.status, Module.STATUS_TESTING)

        # 6. Tester verifies and approves module
        self.client.post(reverse("core:login"), {"username": "testertina", "password": "pass12345"})
        res_verify = self.client.post(reverse("core:module_verify", kwargs={"module_id": module.module_id}))
        self.assertRedirects(res_verify, reverse("core:tester_dashboard"))
        module.refresh_from_db()
        project.refresh_from_db()
        self.assertEqual(module.status, Module.STATUS_COMPLETED)
        self.assertEqual(project.progress, 100)
        self.assertEqual(project.status, Project.STATUS_COMPLETED)
        from core.services.risk_analyzer import calculate_project_risk, predict_project_delay


class RiskAnalyzerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(company_name="RiskCo", email="risk@co.com", address="X")
        self.pm = Employee.objects.create(company=self.company, name="PM", role=Employee.ROLE_PM, email="pm@r.com", username="pmr")
        self.dev = Employee.objects.create(company=self.company, name="Dev", role=Employee.ROLE_DEVELOPER, email="d@r.com", username="devr")
        self.tester = Employee.objects.create(company=self.company, name="Tester", role=Employee.ROLE_TESTER, email="t@r.com", username="testr")

    def test_low_risk_project(self):
        today = date.today()
        project = Project.objects.create(
            company=self.company,
            project_manager=self.pm,
            project_name="Smooth Sailing",
            start_date=today - timedelta(days=5),
            deadline=today + timedelta(days=20),
            progress=50
        )
        risk = calculate_project_risk(project)
        self.assertEqual(risk["risk_level"], "Low")
        self.assertEqual(risk["risk_score"], 0)

    def test_high_risk_project_with_overdue_modules_and_critical_bugs(self):
        today = date.today()
        project = Project.objects.create(
            company=self.company,
            project_manager=self.pm,
            project_name="Troubled Ship",
            start_date=today - timedelta(days=20),
            deadline=today - timedelta(days=1),
            progress=10
        )
        m1 = Module.objects.create(
            project=project, module_name="M1", developer=self.dev, tester=self.tester,
            deadline=today - timedelta(days=5), status=Module.STATUS_IN_PROGRESS
        )
        m2 = Module.objects.create(
            project=project, module_name="M2", developer=self.dev, tester=self.tester,
            deadline=today - timedelta(days=5), status=Module.STATUS_PENDING
        )
        BugReport.objects.create(module=m1, tester=self.tester, developer=self.dev, bug_title="B1", severity=BugReport.SEVERITY_CRITICAL, status=BugReport.STATUS_OPEN)
        BugReport.objects.create(module=m1, tester=self.tester, developer=self.dev, bug_title="B2", severity=BugReport.SEVERITY_HIGH, status=BugReport.STATUS_OPEN)
        BugReport.objects.create(module=m2, tester=self.tester, developer=self.dev, bug_title="B3", severity=BugReport.SEVERITY_CRITICAL, status=BugReport.STATUS_OPEN)

        risk = calculate_project_risk(project)
        self.assertEqual(risk["risk_level"], "High")
        self.assertGreaterEqual(risk["risk_score"], 4)

    def test_predict_project_delay_completed_project(self):
        today = date.today()
        project = Project.objects.create(
            company=self.company,
            project_manager=self.pm,
            project_name="Completed Project",
            start_date=today - timedelta(days=10),
            deadline=today + timedelta(days=10),
            progress=100,
            status=Project.STATUS_COMPLETED
        )
        prediction = predict_project_delay(project)
        self.assertEqual(prediction["status"], "On Track")
        self.assertEqual(prediction["predicted_delay_days"], 0)
        self.assertIn("100% complete", prediction["summary_explanation"])

    def test_predict_project_delay_troubled_project(self):
        today = date.today()
        project = Project.objects.create(
            company=self.company,
            project_manager=self.pm,
            project_name="Delayed Project",
            start_date=today - timedelta(days=15),
            deadline=today + timedelta(days=2),
            progress=20,
            status=Project.STATUS_IN_PROGRESS
        )
        m1 = Module.objects.create(
            project=project, module_name="Task 1", developer=self.dev, tester=self.tester,
            deadline=today - timedelta(days=2), status=Module.STATUS_IN_PROGRESS
        )
        m2 = Module.objects.create(
            project=project, module_name="Task 2", developer=self.dev, tester=self.tester,
            deadline=today - timedelta(days=1), status=Module.STATUS_PENDING
        )
        m3 = Module.objects.create(
            project=project, module_name="Task 3", developer=self.dev, tester=self.tester,
            deadline=today + timedelta(days=1), status=Module.STATUS_PENDING
        )
        BugReport.objects.create(module=m1, tester=self.tester, developer=self.dev, bug_title="Critical Bug", severity=BugReport.SEVERITY_CRITICAL, status=BugReport.STATUS_OPEN)

        prediction = predict_project_delay(project)
        self.assertEqual(prediction["status"], "Likely to be Delayed")
        self.assertGreater(prediction["predicted_delay_days"], 0)
        self.assertTrue(len(prediction["contributing_factors"]) >= 2)
        self.assertIn("confidence_score", prediction)
        self.assertIn("metrics", prediction)


class SecurityAndTenantIsolationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Company 1
        self.co1 = Company.objects.create(company_name="Company One", email="c1@c.com", status=Company.STATUS_APPROVED)
        self.cadmin1 = CompanyAdmin.objects.create(company=self.co1, name="Admin1", email="a1@c.com", username="admin1")
        self.cadmin1.set_password("pass12345")
        self.cadmin1.save()

        self.pm1 = Employee.objects.create(company=self.co1, name="PM1", email="pm1@c.com", role=Employee.ROLE_PM, username="pm1")
        self.pm1.set_password("pass12345")
        self.pm1.save()

        self.dev1 = Employee.objects.create(company=self.co1, name="Dev1", email="dev1@c.com", role=Employee.ROLE_DEVELOPER, username="dev1")
        self.dev1.set_password("pass12345")
        self.dev1.save()

        # Company 2
        self.co2 = Company.objects.create(company_name="Company Two", email="c2@c.com", status=Company.STATUS_APPROVED)
        self.cadmin2 = CompanyAdmin.objects.create(company=self.co2, name="Admin2", email="a2@c.com", username="admin2")
        self.cadmin2.set_password("pass12345")
        self.cadmin2.save()

        self.emp2 = Employee.objects.create(company=self.co2, name="Emp2", email="emp2@c.com", role=Employee.ROLE_DEVELOPER, username="emp2")
        self.emp2.set_password("pass12345")
        self.emp2.save()

    def test_role_authorization_enforcement(self):
        # Developer tries to access Company Admin dashboard -> redirected or forbidden
        self.client.post(reverse("core:login"), {"username": "dev1", "password": "pass12345"})
        res = self.client.get(reverse("core:company_admin_dashboard"))
        self.assertNotEqual(res.status_code, 200)

        # Developer tries to access PM dashboard
        res_pm = self.client.get(reverse("core:pm_dashboard"))
        self.assertNotEqual(res_pm.status_code, 200)

    def test_company_admin_cross_tenant_isolation(self):
        # Admin1 tries to edit Admin2's employee (Emp2) -> should return 404
        self.client.post(reverse("core:login"), {"username": "admin1", "password": "pass12345"})
        res = self.client.get(reverse("core:employee_update", kwargs={"employee_id": self.emp2.employee_id}))
        self.assertEqual(res.status_code, 404)

    def test_employee_deactivation_blocks_login(self):
        self.client.post(reverse("core:login"), {"username": "admin1", "password": "pass12345"})
        # Deactivate Dev1
        self.client.post(reverse("core:employee_deactivate", kwargs={"employee_id": self.dev1.employee_id}))
        self.dev1.refresh_from_db()
        self.assertEqual(self.dev1.status, Employee.STATUS_INACTIVE)

        # Try logging in as Dev1
        res_login = self.client.post(reverse("core:login"), {"username": "dev1", "password": "pass12345"})
        self.assertEqual(res_login.status_code, 200)
        self.assertContains(res_login, "deactivated")

    def test_notification_mark_as_read(self):
        noti = Notification.objects.create(
            sender_id=self.cadmin1.company_admin_id,
            sender_role="Company Admin",
            receiver_id=self.dev1.employee_id,
            receiver_role="Employee",
            message="Test notification",
            notification_type=Notification.TYPE_TASK_COMPLETED,
            status=Notification.STATUS_UNREAD
        )
        self.client.post(reverse("core:login"), {"username": "dev1", "password": "pass12345"})
        res_read = self.client.post(reverse("core:notification_mark_read", kwargs={"notification_id": noti.notification_id}))
        self.assertRedirects(res_read, reverse("core:notification_list"))
        noti.refresh_from_db()
        self.assertEqual(noti.status, Notification.STATUS_READ)

