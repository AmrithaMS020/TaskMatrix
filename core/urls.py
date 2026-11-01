"""
core/urls.py
"""
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing_page, name="landing"),
    path("register/company/", views.company_register, name="company_register"),
    path("login/", views.unified_login, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("global-admin/dashboard/", views.global_admin_dashboard, name="global_admin_dashboard"),
    path("global-admin/companies/", views.company_list, name="company_list"),
    path("global-admin/companies/<int:company_id>/approve/", views.company_approve, name="company_approve"),
    path("global-admin/companies/<int:company_id>/reject/", views.company_reject, name="company_reject"),

    path("company/dashboard/", views.company_admin_dashboard, name="company_admin_dashboard"),
    path("company/employees/", views.employee_list, name="employee_list"),
    path("company/employees/add/", views.employee_create, name="employee_create"),
    path("company/employees/<int:employee_id>/edit/", views.employee_update, name="employee_update"),
    path("company/employees/<int:employee_id>/deactivate/", views.employee_deactivate, name="employee_deactivate"),
    path("company/projects/assign/", views.project_assign, name="project_assign"),

    path("pm/dashboard/", views.pm_dashboard, name="pm_dashboard"),
    path("pm/projects/", views.project_list, name="project_list"),
    path("pm/projects/add/", views.project_create, name="project_create"),
    path("pm/projects/<int:project_id>/", views.project_detail, name="project_detail"),
    path("pm/projects/<int:project_id>/modules/add/", views.module_create, name="module_create"),
    path("pm/projects/<int:project_id>/risk/", views.project_risk_detail, name="project_risk_detail"),

    path("dev/dashboard/", views.developer_dashboard, name="developer_dashboard"),
    path("dev/modules/<int:module_id>/", views.module_detail_dev, name="module_detail_dev"),
    path("dev/modules/<int:module_id>/status/", views.module_update_status, name="module_update_status"),
    path("dev/bugs/<int:bug_id>/resolve/", views.bug_resolve, name="bug_resolve"),

    path("tester/dashboard/", views.tester_dashboard, name="tester_dashboard"),
    path("tester/modules/<int:module_id>/", views.module_detail_test, name="module_detail_test"),
    path("tester/modules/<int:module_id>/verify/", views.module_verify, name="module_verify"),
    path("tester/modules/<int:module_id>/report-bug/", views.bug_report_create, name="bug_report_create"),

    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/<int:notification_id>/read/", views.notification_mark_read, name="notification_mark_read"),
]