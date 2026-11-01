"""
core/auth.py

Lightweight session-based auth helpers. TaskMatrix doesn't use Django's
built-in auth.User (per the SDS, each role stores its own username/password),
so we roll a small decorator instead of @login_required.

Once the real login view is built, it should set:
    request.session["employee_id"] = employee.employee_id
    request.session["employee_role"] = employee.role   # "Developer" / "Tester" / "Project Manager"
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def employee_role_required(*allowed_roles):
    """
    Restrict a view to logged-in Employees whose role is in allowed_roles.
    Usage: @employee_role_required("Developer")
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            employee_id = request.session.get("employee_id")
            employee_role = request.session.get("employee_role")

            if not employee_id or employee_role not in allowed_roles:
                messages.error(request, "Please log in to continue.")
                return redirect("core:login")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def global_admin_required(view_func):
    """Restrict a view to a logged-in Global Admin only."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("global_admin_id"):
            messages.error(request, "Please log in to continue.")
            return redirect("core:login")
        return view_func(request, *args, **kwargs)
    return wrapper


def company_admin_required(view_func):
    """Restrict a view to a logged-in Company Admin only."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("company_admin_id"):
            messages.error(request, "Please log in to continue.")
            return redirect("core:login")
        return view_func(request, *args, **kwargs)
    return wrapper
def any_login_required(view_func):
    """Restrict a view to anyone logged in — any role at all. Used for
    pages shared across roles, like the notification inbox."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not (request.session.get("employee_id")
                or request.session.get("company_admin_id")
                or request.session.get("global_admin_id")):
            messages.error(request, "Please log in to continue.")
            return redirect("core:login")
        return view_func(request, *args, **kwargs)
    return wrapper