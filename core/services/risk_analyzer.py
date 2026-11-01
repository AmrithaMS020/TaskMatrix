"""
core/services/risk_analyzer.py

The AI Project Risk Prediction module described in the SRS.

This is rule-based, automated decision-making — not a trained machine
learning model. That's a deliberate and reasonable choice for this system:
the rules below (overdue modules, unresolved severe bugs, progress lagging
behind the timeline) are exactly the same signals a human Project Manager
would look at to judge whether a project is in trouble, just applied
consistently and automatically every time someone opens the dashboard,
instead of requiring a person to manually re-check three different tables
every time.
"""

from datetime import date, timedelta

from core.models import Module, BugReport, Project, Employee

POINTS_MODULES_MOSTLY_OVERDUE = 2
POINTS_MODULES_SOME_OVERDUE = 1
POINTS_MANY_SEVERE_BUGS = 2
POINTS_SOME_SEVERE_BUGS = 1
POINTS_PROGRESS_LAGGING = 2
POINTS_DEADLINE_PASSED = 2

THRESHOLD_MEDIUM = 2
THRESHOLD_HIGH = 4

SEVERE_BUG_LEVELS = [BugReport.SEVERITY_CRITICAL, BugReport.SEVERITY_HIGH]


def calculate_project_risk(project):
    """
    Evaluate a single Project and return its current risk assessment.

    Returns a dict:
        {
            "risk_level": "Low" | "Medium" | "High",
            "risk_score": int,
            "factors": [str, ...],
        }
    """
    factors = []
    score = 0
    today = date.today()

    modules = Module.objects.filter(project=project)
    total_modules = modules.count()

    if total_modules > 0:
        overdue_count = sum(1 for m in modules if m.is_overdue)
        overdue_ratio = overdue_count / total_modules

        if overdue_ratio > 0.5:
            score += POINTS_MODULES_MOSTLY_OVERDUE
            factors.append(
                f"{overdue_count} of {total_modules} modules "
                f"({overdue_ratio:.0%}) are overdue."
            )
        elif overdue_ratio >= 0.2:
            score += POINTS_MODULES_SOME_OVERDUE
            factors.append(
                f"{overdue_count} of {total_modules} modules "
                f"({overdue_ratio:.0%}) are overdue."
            )

    severe_bug_count = BugReport.objects.filter(
        module__project=project,
        severity__in=SEVERE_BUG_LEVELS,
        status=BugReport.STATUS_OPEN,
    ).count()

    if severe_bug_count >= 3:
        score += POINTS_MANY_SEVERE_BUGS
        factors.append(f"{severe_bug_count} open Critical/High severity bugs.")
    elif severe_bug_count >= 1:
        score += POINTS_SOME_SEVERE_BUGS
        factors.append(f"{severe_bug_count} open Critical/High severity bug(s).")

    if project.status != project.STATUS_COMPLETED:
        total_days = (project.deadline - project.start_date).days
        elapsed_days = (today - project.start_date).days

        if project.deadline < today:
            score += POINTS_DEADLINE_PASSED
            factors.append("Project deadline has already passed.")
        elif total_days > 0:
            timeline_elapsed_ratio = max(0, elapsed_days) / total_days
            if timeline_elapsed_ratio > 0.6 and project.progress < 40:
                score += POINTS_PROGRESS_LAGGING
                factors.append(
                    f"{timeline_elapsed_ratio:.0%} of the timeline has elapsed, "
                    f"but progress is only {project.progress}%."
                )

    if score >= THRESHOLD_HIGH:
        risk_level = "High"
    elif score >= THRESHOLD_MEDIUM:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "risk_level": risk_level,
        "risk_score": score,
        "factors": factors,
    }


def predict_project_delay(project):
    """
    Perform dynamic AI Project Delay Prediction based on real project data.

    Returns a dict:
        {
            "status": "On Track" | "At Risk" | "Likely to be Delayed",
            "status_badge_class": "bg-success" | "bg-warning text-dark" | "bg-danger",
            "predicted_completion_date": date object,
            "predicted_delay_days": int,
            "confidence_score": int (0-100),
            "contributing_factors": [str, ...],
            "summary_explanation": str,
            "metrics": dict of raw project health stats
        }
    """
    today = date.today()
    modules = list(project.modules.all())
    total_modules = len(modules)
    completed_modules = sum(1 for m in modules if m.status == Module.STATUS_COMPLETED)
    pending_modules = total_modules - completed_modules
    overdue_modules = sum(1 for m in modules if m.is_overdue)
    
    completion_rate = round((completed_modules / total_modules * 100)) if total_modules > 0 else (100 if project.status == Project.STATUS_COMPLETED else 0)

    # Bugs query
    bugs = BugReport.objects.filter(module__project=project)
    total_bugs = bugs.count()
    unresolved_bugs = bugs.exclude(status=BugReport.STATUS_CLOSED)
    unresolved_bugs_count = unresolved_bugs.count()
    critical_high_bugs = unresolved_bugs.filter(severity__in=[BugReport.SEVERITY_CRITICAL, BugReport.SEVERITY_HIGH]).count()

    # Developers workload
    dev_ids = [m.developer_id for m in modules if m.developer_id]
    if dev_ids:
        active_dev_count = len(set(dev_ids))
        total_dev_active_tasks = Module.objects.filter(
            developer_id__in=dev_ids
        ).exclude(status=Module.STATUS_COMPLETED).count()
        avg_workload_tasks = total_dev_active_tasks / active_dev_count
    else:
        active_dev_count = 1
        avg_workload_tasks = pending_modules

    if avg_workload_tasks >= 4:
        team_workload_label = "High"
        workload_multiplier = 1.25
    elif avg_workload_tasks >= 2:
        team_workload_label = "Medium"
        workload_multiplier = 1.10
    else:
        team_workload_label = "Low"
        workload_multiplier = 1.00

    # Historical task duration
    completed_mods_company = Module.objects.filter(
        project__company=project.company,
        status=Module.STATUS_COMPLETED,
        completed_date__isnull=False
    )
    if completed_mods_company.exists():
        total_days_spent = sum(max(1, (m.completed_date - m.assigned_date).days) for m in completed_mods_company)
        avg_task_days = total_days_spent / completed_mods_company.count()
    else:
        avg_task_days = 3.0

    avg_task_days = max(1.0, avg_task_days)

    # If project is already completed
    if project.status == Project.STATUS_COMPLETED or (total_modules > 0 and pending_modules == 0 and unresolved_bugs_count == 0):
        return {
            "status": "On Track",
            "status_badge_class": "bg-success",
            "risk_level": "Low",
            "predicted_completion_date": project.deadline,
            "predicted_delay_days": 0,
            "confidence_score": 98,
            "contributing_factors": ["All project modules have been successfully completed and verified."],
            "summary_explanation": "Project is 100% complete and on schedule.",
            "metrics": {
                "total_modules": total_modules,
                "completed_modules": completed_modules,
                "pending_modules": 0,
                "overdue_modules": 0,
                "completion_rate": 100,
                "unresolved_bugs": 0,
                "critical_high_bugs": 0,
                "team_workload": team_workload_label,
                "avg_task_days": round(avg_task_days, 1),
                "remaining_days": 0,
            }
        }

    # Velocity and execution time estimation
    capacity = max(1, active_dev_count)
    base_remaining_execution_days = (pending_modules * avg_task_days) / capacity
    
    # Impact buffers
    overdue_penalty_days = overdue_modules * 1.5
    bug_resolution_days = (critical_high_bugs * 1.5) + ((unresolved_bugs_count - critical_high_bugs) * 0.75)
    
    total_estimated_needed_days = round((base_remaining_execution_days * workload_multiplier) + overdue_penalty_days + bug_resolution_days)
    if pending_modules > 0 or unresolved_bugs_count > 0:
        total_estimated_needed_days = max(1, total_estimated_needed_days)
    else:
        total_estimated_needed_days = 0

    projected_completion_date = today + timedelta(days=total_estimated_needed_days)
    
    # Calculate delay in days compared to planned deadline
    if project.deadline < today:
        days_already_overdue = (today - project.deadline).days
        predicted_delay_days = days_already_overdue + total_estimated_needed_days
    else:
        raw_delay = (projected_completion_date - project.deadline).days
        predicted_delay_days = max(0, raw_delay)

    # Status classification & factors
    factors = []
    
    if overdue_modules > 0:
        factors.append(f"{overdue_modules} of {total_modules} task(s) are overdue past their deadline.")
    if pending_modules > 0:
        factors.append(f"{pending_modules} pending task(s) remaining to be finished.")
    if unresolved_bugs_count > 0:
        if critical_high_bugs > 0:
            factors.append(f"{unresolved_bugs_count} unresolved bug(s), including {critical_high_bugs} Critical/High severity.")
        else:
            factors.append(f"{unresolved_bugs_count} unresolved bug(s) pending resolution.")
    if team_workload_label == "High":
        factors.append(f"High team workload (avg {avg_workload_tasks:.1f} active tasks per developer).")

    # Timeline elapsed vs progress lag
    total_planned_duration = max(1, (project.deadline - project.start_date).days)
    elapsed_duration = (today - project.start_date).days
    if project.deadline < today:
        days_past = (today - project.deadline).days
        factors.append(f"Project deadline passed on {project.deadline.strftime('%d %b %Y')} ({days_past} days ago).")
    elif total_planned_duration > 0 and elapsed_duration > 0:
        elapsed_ratio = elapsed_duration / total_planned_duration
        if elapsed_ratio > 0.5 and completion_rate < 50:
            factors.append(f"Timeline is {elapsed_ratio:.0%} elapsed, but completion rate is only {completion_rate}%.")

    if not factors:
        factors.append("Task completion velocity is on target for the planned deadline.")
        factors.append("No critical bug blockers detected.")

    if predicted_delay_days > 3 or overdue_modules >= 2 or (critical_high_bugs >= 2 and pending_modules > 2):
        status = "Likely to be Delayed"
        status_badge_class = "bg-danger"
        risk_level = "High"
    elif predicted_delay_days > 0 or overdue_modules > 0 or unresolved_bugs_count >= 2:
        status = "At Risk"
        status_badge_class = "bg-warning text-dark"
        risk_level = "Medium"
    else:
        status = "On Track"
        status_badge_class = "bg-success"
        risk_level = "Low"

    # Confidence score calculation
    confidence_score = min(94, max(72, 75 + (completed_modules * 3) + (5 if total_modules >= 3 else 0)))

    # PM Summary Explanation
    if predicted_delay_days > 0:
        summary_explanation = (
            f"Based on current task progress ({completion_rate}%), {pending_modules} pending task(s), "
            f"and {unresolved_bugs_count} unresolved bug(s), the AI estimates project completion around "
            f"{projected_completion_date.strftime('%d %B %Y')}, resulting in a predicted delay of ~{predicted_delay_days} day(s)."
        )
    else:
        summary_explanation = (
            f"The project is currently progressing well with a {completion_rate}% completion rate. "
            f"Current velocity indicates completion on or before the planned deadline ({project.deadline.strftime('%d %B %Y')})."
        )

    return {
        "status": status,
        "status_badge_class": status_badge_class,
        "risk_level": risk_level,
        "predicted_completion_date": projected_completion_date,
        "predicted_delay_days": predicted_delay_days,
        "confidence_score": confidence_score,
        "contributing_factors": factors,
        "summary_explanation": summary_explanation,
        "metrics": {
            "total_modules": total_modules,
            "completed_modules": completed_modules,
            "pending_modules": pending_modules,
            "overdue_modules": overdue_modules,
            "completion_rate": completion_rate,
            "unresolved_bugs": unresolved_bugs_count,
            "critical_high_bugs": critical_high_bugs,
            "team_workload": team_workload_label,
            "avg_task_days": round(avg_task_days, 1),
            "remaining_days": max(0, (project.deadline - today).days),
        }
    }