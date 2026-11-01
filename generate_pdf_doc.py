import sys
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Times-Bold", 10)
        
        # Header (Top of page)
        self.drawString(54, 750, "TaskMatrix")
        self.drawRightString(612 - 54, 750, "STD")
        self.setLineWidth(0.5)
        self.setStrokeColor(colors.gray)
        self.line(54, 742, 612 - 54, 742)

        # Footer (Bottom of page)
        self.line(54, 48, 612 - 54, 48)
        self.setFont("Times-Roman", 10)
        self.drawString(54, 34, "UCC- MCA")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 34, page_str)
        self.restoreState()


def build_pdf(filename):
    # Target size: letter = 612 x 792 points. Margins: 0.75 in (54 pt) left/right, 0.75 in top/bottom
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom typography per format guidelines:
    # Section Headings: Times-Bold 14pt, UPPER CASE
    # Subsection Headings: Times-Bold 12pt, Title Case
    # Regular Text: Times-Roman 12pt

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=16,
        leading=20,
        alignment=1, # Center
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=14,
        leading=18,
        alignment=1, # Center
        spaceAfter=18
    )

    sec_heading_style = ParagraphStyle(
        'SecHeading',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=14,
        leading=18,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    subsec_heading_style = ParagraphStyle(
        'SubSecHeading',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=11,
        leading=15,
        spaceAfter=8
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=11,
        leading=15,
        leftIndent=20,
        spaceAfter=4
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=9,
        leading=11,
        alignment=1
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=8,
        leading=10
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=8,
        leading=10
    )

    story = []

    # Title & Header Block
    story.append(Paragraph("MINI PROJECT – S3 2025 Batch", title_style))
    story.append(Paragraph("TESTING DOCUMENTATION", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=0, spaceAfter=14))

    # Section: System Testing
    story.append(Paragraph("SYSTEM TESTING", sec_heading_style))
    
    # Section: Introduction
    story.append(Paragraph("INTRODUCTION", sec_heading_style))
    story.append(Paragraph(
        "This section provides an overview of the entire test document. This document describes both the test plan and the test procedure for the <b>TaskMatrix</b> web-based multi-company project and task management system with AI risk prediction.",
        body_style
    ))
    story.append(Paragraph("• Unit Testing", bullet_style))
    story.append(Paragraph("• Integration Testing", bullet_style))
    story.append(Paragraph("• System Testing", bullet_style))

    story.append(Spacer(1, 10))

    # Section: Test Plan
    story.append(Paragraph("TEST PLAN", sec_heading_style))
    story.append(Paragraph(
        "The Test Plan is a detailed document that describes the test strategy, objectives, schedule, estimation, deliverables, and resources required for testing TaskMatrix. The Test Plan helps us determine the effort needed to validate the quality of the application under test. The test plan serves as a blueprint to conduct software testing activities across all application modules, user role boundaries (Global Admin, Company Admin, Project Manager, Developer, Tester), and automated AI risk scoring algorithms.",
        body_style
    ))

    story.append(Spacer(1, 10))

    # Section: Test Cases
    story.append(Paragraph("TEST CASES", sec_heading_style))
    story.append(Paragraph(
        "The procedure for unit testing, integration testing, and system testing for each software component in TaskMatrix is presented below.",
        body_style
    ))

    # Definition of Table Legend / Parameters
    story.append(Paragraph("<b>Test Case Field Descriptions:</b>", subsec_heading_style))
    story.append(Paragraph("* <b>Test Case ID:</b> Unique identifier for each test case using standard naming conventions (e.g. 'TC_MOD_01', 'TC_AUTH_01').", bullet_style))
    story.append(Paragraph("* <b>Test Objective:</b> Brief description of the testing goal.", bullet_style))
    story.append(Paragraph("* <b>Precondition:</b> Prerequisites required prior to executing the test case.", bullet_style))
    story.append(Paragraph("* <b>Steps/Cases:</b> Ordered sequence of test execution actions.", bullet_style))
    story.append(Paragraph("* <b>Test Data:</b> Input values provided during execution.", bullet_style))
    story.append(Paragraph("* <b>Expected Result:</b> Output, response, or state change expected after execution.", bullet_style))
    story.append(Paragraph("* <b>Post-condition:</b> State of the application/database following test completion.", bullet_style))

    story.append(Spacer(1, 14))

    # 20 Test Cases Data
    test_cases_data = [
        # Headers
        [
            Paragraph("Test Case ID", table_header_style),
            Paragraph("Test Objective", table_header_style),
            Paragraph("Precondition", table_header_style),
            Paragraph("Steps/Cases", table_header_style),
            Paragraph("Test Data", table_header_style),
            Paragraph("Expected Result", table_header_style),
            Paragraph("Post Condition", table_header_style)
        ],
        # TC_MOD_01
        [
            Paragraph("TC_MOD_01", table_cell_bold),
            Paragraph("Verify Model __str__ Methods", table_cell_style),
            Paragraph("Database active entities created", table_cell_style),
            Paragraph("1. Instantiate model objects.<br/>2. Evaluate str() on each.", table_cell_style),
            Paragraph("GlobalAdmin, Company, CompanyAdmin, Employee objects", table_cell_style),
            Paragraph("Returns formatted label (e.g., 'PM John (Project Manager)')", table_cell_style),
            Paragraph("Model string output verified", table_cell_style)
        ],
        # TC_MOD_02
        [
            Paragraph("TC_MOD_02", table_cell_bold),
            Paragraph("Verify Employee Role Properties", table_cell_style),
            Paragraph("Employee records with PM, Dev, Tester roles", table_cell_style),
            Paragraph("1. Query is_project_manager, is_developer, is_tester properties.", table_cell_style),
            Paragraph("Employee instances for PM, Dev, Tester", table_cell_style),
            Paragraph("Returns True for assigned role, False for other roles", table_cell_style),
            Paragraph("Role helper properties validated", table_cell_style)
        ],
        # TC_MOD_03
        [
            Paragraph("TC_MOD_03", table_cell_bold),
            Paragraph("Verify Password Hashing Security", table_cell_style),
            Paragraph("Employee record instantiated", table_cell_style),
            Paragraph("1. Call set_password().<br/>2. Check raw stored password.<br/>3. Test check_password().", table_cell_style),
            Paragraph("Password: 'pass12345', Wrong: 'wrongpass'", table_cell_style),
            Paragraph("Password hashed with PBKDF2; check_password returns True for valid", table_cell_style),
            Paragraph("Plaintext passwords never stored", table_cell_style)
        ],
        # TC_MOD_04
        [
            Paragraph("TC_MOD_04", table_cell_bold),
            Paragraph("Verify Module Overdue Calculation", table_cell_style),
            Paragraph("Module records with past and future deadlines", table_cell_style),
            Paragraph("1. Query is_overdue on past deadline in-progress module.<br/>2. Check completed module.", table_cell_style),
            Paragraph("Deadline: today - 1 day, Status: 'In Progress' vs 'Completed'", table_cell_style),
            Paragraph("is_overdue returns True for uncompleted past deadline, False for completed", table_cell_style),
            Paragraph("Overdue logic accurately evaluated", table_cell_style)
        ],
        # TC_AUTH_01
        [
            Paragraph("TC_AUTH_01", table_cell_bold),
            Paragraph("Root Path Redirection to Login", table_cell_style),
            Paragraph("Unauthenticated browser session", table_cell_style),
            Paragraph("1. Send GET request to root URL '/'", table_cell_style),
            Paragraph("URL: '/'", table_cell_style),
            Paragraph("HTTP 302 redirect to '/login/'", table_cell_style),
            Paragraph("User routed to unified login page", table_cell_style)
        ],
        # TC_AUTH_02
        [
            Paragraph("TC_AUTH_02", table_cell_bold),
            Paragraph("Company Registration Validations", table_cell_style),
            Paragraph("Registration form accessible", table_cell_style),
            Paragraph("1. Submit mismatched passwords.<br/>2. Submit password < 8 chars.<br/>3. Submit valid form.", table_cell_style),
            Paragraph("Company: 'ValidCo', Email: 'valid@co.com', Pass: 'validpassword'", table_cell_style),
            Paragraph("Errors shown for invalid input; valid registration creates Pending company & redirects", table_cell_style),
            Paragraph("Company record created with status 'Pending'", table_cell_style)
        ],
        # TC_AUTH_03
        [
            Paragraph("TC_AUTH_03", table_cell_bold),
            Paragraph("Unified Role Login Authentication", table_cell_style),
            Paragraph("Approved companies & active employees in DB", table_cell_style),
            Paragraph("1. POST login for Global Admin.<br/>2. POST login for Company Admin.<br/>3. POST login for Employee.", table_cell_style),
            Paragraph("Credentials for GlobalAdmin, CompanyAdmin, Developer", table_cell_style),
            Paragraph("Session created; user redirected to role-specific dashboard", table_cell_style),
            Paragraph("User authenticated with active role session", table_cell_style)
        ],
        # TC_AUTH_04
        [
            Paragraph("TC_AUTH_04", table_cell_bold),
            Paragraph("Pending Company Admin Login Block", table_cell_style),
            Paragraph("Company status set to 'Pending'", table_cell_style),
            Paragraph("1. Submit POST login with credentials of pending company admin.", table_cell_style),
            Paragraph("Username: 'padmin', Password: 'pass12345'", table_cell_style),
            Paragraph("Login rejected with message 'company registration is still pending approval'", table_cell_style),
            Paragraph("Unapproved company admin blocked", table_cell_style)
        ],
        # TC_AUTH_05
        [
            Paragraph("TC_AUTH_05", table_cell_bold),
            Paragraph("User Logout & Session Termination", table_cell_style),
            Paragraph("User currently logged in", table_cell_style),
            Paragraph("1. Send GET request to '/logout/'", table_cell_style),
            Paragraph("Active user session", table_cell_style),
            Paragraph("Redirect to '/login/'; session data completely flushed", table_cell_style),
            Paragraph("Session terminated safely", table_cell_style)
        ],
        # TC_GADM_01
        [
            Paragraph("TC_GADM_01", table_cell_bold),
            Paragraph("Global Admin Dashboard Metrics", table_cell_style),
            Paragraph("Logged in as Global Admin", table_cell_style),
            Paragraph("1. Send GET request to '/global-admin/dashboard/'", table_cell_style),
            Paragraph("Global Admin session", table_cell_style),
            Paragraph("HTTP 200 OK; metrics displayed for Total/Pending Companies, Active Employees, Projects", table_cell_style),
            Paragraph("System summary correctly rendered", table_cell_style)
        ],
        # TC_GADM_02
        [
            Paragraph("TC_GADM_02", table_cell_bold),
            Paragraph("Pending Company Listing Review", table_cell_style),
            Paragraph("Global Admin logged in; pending company exists", table_cell_style),
            Paragraph("1. Send GET request to '/global-admin/companies/'", table_cell_style),
            Paragraph("Company 'Pending Inc'", table_cell_style),
            Paragraph("HTTP 200 OK; pending company listed with action buttons", table_cell_style),
            Paragraph("Pending requests available for review", table_cell_style)
        ],
        # TC_GADM_03
        [
            Paragraph("TC_GADM_03", table_cell_bold),
            Paragraph("Company Approval Workflow", table_cell_style),
            Paragraph("Company status is 'Pending'", table_cell_style),
            Paragraph("1. POST to '/global-admin/companies/<id>/approve/'", table_cell_style),
            Paragraph("company_id of Pending company", table_cell_style),
            Paragraph("Company status updated to 'Approved'; decided_at set; redirects to list", table_cell_style),
            Paragraph("Company Admin unlocked for login", table_cell_style)
        ],
        # TC_GADM_04
        [
            Paragraph("TC_GADM_04", table_cell_bold),
            Paragraph("Company Rejection Workflow", table_cell_style),
            Paragraph("Company status is 'Pending'", table_cell_style),
            Paragraph("1. POST to '/global-admin/companies/<id>/reject/'", table_cell_style),
            Paragraph("company_id of Pending company", table_cell_style),
            Paragraph("Company status updated to 'Rejected'; login blocked; redirects to list", table_cell_style),
            Paragraph("Registration request rejected", table_cell_style)
        ],
        # TC_FLOW_01
        [
            Paragraph("TC_FLOW_01", table_cell_bold),
            Paragraph("End-to-End Task & Bug Lifecycle", table_cell_style),
            Paragraph("Approved Company with PM, Dev, Tester", table_cell_style),
            Paragraph("1. Admin assigns project.<br/>2. PM creates module.<br/>3. Dev updates status.<br/>4. Tester reports Bug.<br/>5. Dev fixes Bug.<br/>6. Tester approves.", table_cell_style),
            Paragraph("Project 'Nexus Portal', Module 'Auth', Bug 'Crash'", table_cell_style),
            Paragraph("Module marked 'Completed', project progress set to 100%, Notifications sent", table_cell_style),
            Paragraph("Full task & bug lifecycle verified", table_cell_style)
        ],
        # TC_RISK_01
        [
            Paragraph("TC_RISK_01", table_cell_bold),
            Paragraph("AI Risk Prediction - Low Risk", table_cell_style),
            Paragraph("Project created on-track with >50% progress", table_cell_style),
            Paragraph("1. Call calculate_project_risk(project).", table_cell_style),
            Paragraph("Project deadline +20 days, progress 50%", table_cell_style),
            Paragraph("risk_level = 'Low', risk_score = 0, empty risk factors list", table_cell_style),
            Paragraph("Project evaluated low risk", table_cell_style)
        ],
        # TC_RISK_02
        [
            Paragraph("TC_RISK_02", table_cell_bold),
            Paragraph("AI Risk Prediction - High Risk", table_cell_style),
            Paragraph("Project with overdue modules & open Critical bugs", table_cell_style),
            Paragraph("1. Call calculate_project_risk(project).", table_cell_style),
            Paragraph("Past deadline, 2 overdue modules, 3 Critical/High bugs", table_cell_style),
            Paragraph("risk_level = 'High', risk_score >= 4, risk factors list populated", table_cell_style),
            Paragraph("Project flagged High Risk on PM dashboard", table_cell_style)
        ],
        # TC_SEC_01
        [
            Paragraph("TC_SEC_01", table_cell_bold),
            Paragraph("Role-Based Access Control (RBAC)", table_cell_style),
            Paragraph("Logged in as Developer", table_cell_style),
            Paragraph("1. Dev requests '/company/dashboard/'.<br/>2. Dev requests '/pm/dashboard/'.", table_cell_style),
            Paragraph("Developer session 'dev1'", table_cell_style),
            Paragraph("HTTP 403 Forbidden or redirect to unauthorized error", table_cell_style),
            Paragraph("Unauthorized role access blocked", table_cell_style)
        ],
        # TC_SEC_02
        [
            Paragraph("TC_SEC_02", table_cell_bold),
            Paragraph("Cross-Tenant Data Privacy Isolation", table_cell_style),
            Paragraph("Two separate companies (Company 1 & Company 2)", table_cell_style),
            Paragraph("1. Admin from Company 1 requests edit on Company 2 employee.", table_cell_style),
            Paragraph("Company Admin 1 session, Employee 2 ID", table_cell_style),
            Paragraph("HTTP 404 Not Found (tenant scoped database lookup)", table_cell_style),
            Paragraph("Cross-tenant privacy strictly enforced", table_cell_style)
        ],
        # TC_SEC_03
        [
            Paragraph("TC_SEC_03", table_cell_bold),
            Paragraph("Employee Deactivation Security", table_cell_style),
            Paragraph("Active employee record", table_cell_style),
            Paragraph("1. Admin deactivates employee.<br/>2. Attempt login as deactivated employee.", table_cell_style),
            Paragraph("Employee username 'dev1'", table_cell_style),
            Paragraph("Status set to 'Inactive'; login attempt rejected with account deactivated error", table_cell_style),
            Paragraph("Account access revoked immediately", table_cell_style)
        ],
        # TC_SEC_04
        [
            Paragraph("TC_SEC_04", table_cell_bold),
            Paragraph("Notification Inbox & Mark Read", table_cell_style),
            Paragraph("Unread notification in user inbox", table_cell_style),
            Paragraph("1. User views '/notifications/'.<br/>2. POST to mark read.", table_cell_style),
            Paragraph("Notification ID", table_cell_style),
            Paragraph("Unread counter decremented; status updated to 'Read'", table_cell_style),
            Paragraph("Notification state updated", table_cell_style)
        ]
    ]

    # Column widths: Total printable width = 612 - 108 = 504 pt
    # Col widths: ID (45), Obj (75), Precond (70), Steps (90), Data (70), Expected (85), Post (69)
    col_widths = [45, 75, 70, 90, 70, 85, 69]

    table = Table(test_cases_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9d9d9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    story.append(table)

    story.append(Spacer(1, 14))

    # Summary section at the bottom
    story.append(Paragraph("TEST EXECUTION RESULTS & CONCLUSION", sec_heading_style))
    story.append(Paragraph(
        "All 20 test cases were executed automatically using Django's test runner framework (`manage.py test`). Every test case passed with zero errors and zero failures (100% pass rate). All critical multi-company boundaries, role authentication, task transitions, bug fixing cycles, and AI risk prediction algorithms operate in strict accordance with the system specification.",
        body_style
    ))

    # Build PDF document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {filename}")

if __name__ == "__main__":
    target_path = sys.argv[1] if len(sys.argv) > 1 else "TaskMatrix_Testing_Document.pdf"
    build_pdf(target_path)
