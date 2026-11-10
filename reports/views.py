from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import (
    Avg, Count, ExpressionWrapper, F, FloatField, Max, Q, Sum,
)
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from academics.access import teacher_classes, teacher_subjects
from academics.models import AcademicYear, SchoolClass, Subject
from accounts.mixins import role_required
from attendance.models import Attendance
from examinations.models import Result
from finance.models import Payment
from students.models import Student
from teachers.models import Teacher

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
except ImportError:  # pragma: no cover
    Workbook = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:  # pragma: no cover
    colors = None


def _excel_response(filename, headers, rows, title):
    if Workbook is None:
        return HttpResponse('openpyxl is required to export Excel files.', status=500)
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    header_fill = PatternFill('solid', fgColor='0B2545')
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    for row in rows:
        ws.append([_excel_safe_value(value) for value in row])
    for column in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column)
        ws.column_dimensions[column[0].column_letter].width = min(max_length + 4, 40)
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    wb.save(response)
    return response


def _excel_safe_value(value):
    if not isinstance(value, str):
        return value
    value = ''.join(
        character
        for character in value
        if character in '\t\n\r'
        or (
            ord(character) >= 32
            and not 127 <= ord(character) <= 159
        )
    )
    if value.lstrip().startswith(('=', '+', '-', '@')):
        return f"'{value}"
    return value


def _pdf_response(filename, title, headers, rows):
    if colors is None:
        return HttpResponse('reportlab is required to export PDF files.', status=500)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    doc = SimpleDocTemplate(
        response, pagesize=landscape(A4), topMargin=14 * mm, bottomMargin=14 * mm,
        leftMargin=14 * mm, rightMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(settings.SCHOOL_NAME, styles['Title']),
        Paragraph(settings.SCHOOL_ADDRESS, styles['Normal']),
        Paragraph(settings.SCHOOL_PHONE, styles['Normal']),
        Spacer(1, 6),
        Paragraph(title, styles['Heading2']),
        Paragraph(
            f'Generated {timezone.now().strftime("%d %b %Y %H:%M")}', styles['Italic']
        ),
        Spacer(1, 10),
    ]
    data = [headers] + [list(row) for row in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c5a35')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#dce6df')),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f8f5')]),
    ]))
    story.append(table)
    doc.build(story)
    return response


@role_required('teacher', 'accountant', 'dos')
def reports_index(request):
    context = {
        'page_title': 'Reports & Exports',
        'is_teacher': False,
        'is_dos': False,
    }
    if request.user.role == 'teacher':
        classes = teacher_classes(request.user)
        context.update({
            'is_teacher': True,
            'student_count': Student.objects.filter(
                school_class__in=classes, is_archived=False
            ).count(),
            'class_count': classes.count(),
            'subject_count': teacher_subjects(request.user).count(),
        })
    elif request.user.role == 'dos':
        from academics.models import AcademicYear
        current_year = AcademicYear.objects.filter(is_current=True).first()
        classes = SchoolClass.objects.all()
        subjects = Subject.objects.filter(is_active=True)
        if current_year:
            classes = classes.filter(academic_year=current_year)
            subjects = subjects.filter(academic_year=current_year)
        context.update({
            'is_dos': True,
            'student_count': Student.objects.filter(
                school_class__in=classes, status=Student.Status.ACTIVE,
                is_archived=False,
            ).count(),
            'class_count': classes.count(),
            'subject_count': subjects.count(),
            'exam_count': (
                current_year.examinations.count() if current_year else 0
            ),
        })
    else:
        context.update({
            'student_count': Student.objects.filter(is_archived=False).count(),
            'teacher_count': Teacher.objects.count(),
            'class_count': SchoolClass.objects.count(),
            'payment_total': Payment.objects.aggregate(total=Sum('amount'))['total'] or 0,
        })
    return render(request, 'reports/index.html', context)


@role_required('accountant')
def export_students(request, fmt):
    students = Student.objects.filter(is_archived=False).select_related(
        'user', 'school_class', 'department'
    )
    class_id = request.GET.get('school_class', '')
    if class_id:
        students = students.filter(school_class_id=class_id)
    headers = [
        'Student ID', 'Full Name', 'Class', 'Department', 'Gender', 'Status',
        'Admission Date', 'Email', 'Phone',
    ]
    rows = [
        [
            student.student_id, student.full_name,
            student.school_class.name if student.school_class else '',
            student.department.name if student.department else '',
            student.get_gender_display(), student.get_status_display(),
            student.admission_date.strftime('%Y-%m-%d'), student.user.email, student.user.phone,
        ]
        for student in students
    ]
    if fmt == 'excel':
        return _excel_response('students-report', headers, rows, 'Students')
    return _pdf_response('students-report', 'Student Registration Report', headers, rows)


@role_required('accountant')
def export_teachers(request, fmt):
    teachers = Teacher.objects.select_related('user', 'department')
    headers = ['Staff ID', 'Full Name', 'Department', 'Qualification', 'Specialization', 'Employment', 'Status']
    rows = [
        [
            teacher.staff_id, teacher.full_name,
            teacher.department.name if teacher.department else '',
            teacher.qualification, teacher.specialization,
            teacher.get_employment_type_display(), teacher.get_status_display(),
        ]
        for teacher in teachers
    ]
    if fmt == 'excel':
        return _excel_response('teachers-report', headers, rows, 'Teachers')
    return _pdf_response('teachers-report', 'Teacher Information Report', headers, rows)


@role_required('teacher', 'student', 'parent', 'accountant', 'dos')
def export_attendance(request, fmt):
    records = Attendance.objects.select_related(
        'student__user', 'school_class', 'subject'
    )
    if request.user.role == 'teacher':
        records = records.filter(
            Q(school_class__subjects__teacher=request.user)
            | Q(school_class__class_teacher=request.user)
        ).distinct()
    elif request.user.role == 'student':
        records = records.filter(student__user=request.user)
    elif request.user.role == 'parent':
        records = records.filter(student__parent__user=request.user)
    class_id = request.GET.get('school_class', '')
    start = request.GET.get('start_date', '')
    end = request.GET.get('end_date', '')
    if class_id:
        records = records.filter(school_class_id=class_id)
    if start:
        records = records.filter(date__gte=start)
    if end:
        records = records.filter(date__lte=end)
    headers = ['Date', 'Student ID', 'Student', 'Class', 'Subject', 'Status', 'Remarks']
    rows = [
        [
            record.date.strftime('%Y-%m-%d'), record.student.student_id,
            record.student.full_name, record.school_class.name,
            record.subject.name if record.subject else 'Daily',
            record.get_status_display(), record.remarks,
        ]
        for record in records
    ]
    if fmt == 'excel':
        return _excel_response('attendance-report', headers, rows, 'Attendance')
    return _pdf_response('attendance-report', 'Attendance Report', headers, rows)


@role_required('teacher', 'accountant', 'dos')
def export_results(request, fmt):
    results = Result.objects.select_related(
        'student__user', 'student__school_class', 'examination', 'subject'
    )
    if request.user.role == 'teacher':
        results = results.filter(
            Q(subject__teacher=request.user)
            | Q(
                student__school_class__class_teacher=request.user,
                subject__school_classes=F('student__school_class'),
            )
        ).distinct()
    elif request.user.role == 'student':
        results = results.filter(student__user=request.user)
    elif request.user.role == 'parent':
        results = results.filter(student__parent__user=request.user)
    exam_id = request.GET.get('examination', '')
    class_id = request.GET.get('school_class', '')
    if exam_id:
        results = results.filter(examination_id=exam_id)
    if class_id:
        results = results.filter(student__school_class_id=class_id)

    headers = ['Exam', 'Student ID', 'Student', 'Class', 'Subject', 'Marks', 'Total', 'Percentage', 'Grade']
    rows = [
        [
            result.examination.name, result.student.student_id, result.student.full_name,
            result.student.school_class.name if result.student.school_class else '',
            result.subject.name, float(result.marks_obtained), float(result.total_marks),
            f'{result.percentage}%', result.grade,
        ]
        for result in results
    ]
    if fmt == 'excel':
        return _excel_response('results-report', headers, rows, 'Results')
    return _pdf_response('results-report', 'Examination Results Report', headers, rows)


@role_required('accountant')
def export_finance(request, fmt):
    payments = Payment.objects.select_related('student__user', 'student__school_class', 'fee')
    start = request.GET.get('start_date', '')
    end = request.GET.get('end_date', '')
    if start:
        payments = payments.filter(payment_date__gte=start)
    if end:
        payments = payments.filter(payment_date__lte=end)
    headers = ['Receipt', 'Date', 'Student ID', 'Student', 'Class', 'Fee', 'Method', 'Amount']
    rows = [
        [
            payment.receipt_number, payment.payment_date.strftime('%Y-%m-%d'),
            payment.student.student_id, payment.student.full_name,
            payment.student.school_class.name if payment.student.school_class else '',
            payment.fee.name if payment.fee else 'General',
            payment.get_method_display(), float(payment.amount),
        ]
        for payment in payments
    ]
    if fmt == 'excel':
        return _excel_response('finance-report', headers, rows, 'Finance')
    return _pdf_response('finance-report', 'Financial Transactions Report', headers, rows)


@role_required('teacher', 'accountant', 'dos')
def class_performance(request):
    results = Result.objects.select_related('student__school_class')
    class_id = request.GET.get('school_class', '')
    if class_id:
        results = results.filter(student__school_class_id=class_id)
    if request.user.role == 'teacher':
        results = results.filter(
            Q(subject__teacher=request.user)
            | Q(
                student__school_class__class_teacher=request.user,
                subject__school_classes=F('student__school_class'),
            )
        ).distinct()

    summary = (
        results.values('student__school_class__name', 'student__school_class_id')
        .annotate(
            entries=Count('id'),
            average=Avg('marks_obtained'),
            highest=Max('marks_obtained'),
        )
        .order_by('student__school_class__name')
    )
    classes = SchoolClass.objects.all().order_by('name')
    if request.user.role == 'teacher':
        classes = teacher_classes(request.user).order_by('name')
    return render(request, 'reports/class_performance.html', {
        'page_title': 'Class Performance',
        'summary': summary,
        'classes': classes,
        'selected_class': class_id,
    })


def _performance_value(results):
    return results.aggregate(
        average=Avg(ExpressionWrapper(
            F('marks_obtained') * 100.0 / F('total_marks'),
            output_field=FloatField(),
        )),
        entries=Count('pk'),
    )


def _academic_report_response(request, title, headers, rows, description):
    output_format = request.GET.get('format', '')
    if output_format in ('excel', 'pdf'):
        if output_format == 'excel':
            return _excel_response(
                title.lower().replace(' ', '-'), headers, rows, title[:31]
            )
        return _pdf_response(
            title.lower().replace(' ', '-'), title, headers, rows
        )
    return render(request, 'reports/academic_performance.html', {
        'page_title': title,
        'report_title': title,
        'report_description': description,
        'headers': headers,
        'rows': rows,
        'academic_years': AcademicYear.objects.order_by('-start_date'),
        'selected_year': request.GET.get('academic_year', ''),
        'selected_format': output_format,
    })


@role_required('dos')
def teacher_performance(request):
    from academics.access import teacher_subjects
    from academics.models import AcademicYear, LessonPlan, TeachingObservation
    from teachers.models import Teacher

    year_id = request.GET.get('academic_year', '').strip()
    year = AcademicYear.objects.filter(pk=year_id).first() if year_id.isdigit() else None
    teachers = Teacher.objects.filter(
        status=Teacher.Status.ACTIVE
    ).select_related('user', 'department')
    headers = [
        'Staff ID', 'Teacher', 'Department', 'Subjects', 'Lessons submitted',
        'Plans approved', 'Average observation rating', 'Average student marks (%)',
    ]
    rows = []
    for teacher in teachers:
        subjects = teacher_subjects(teacher.user)
        plans = LessonPlan.objects.filter(teacher=teacher.user)
        observations = TeachingObservation.objects.filter(teacher=teacher.user)
        results = Result.objects.filter(subject__in=subjects)
        if year:
            subjects = subjects.filter(academic_year=year)
            plans = plans.filter(academic_year=year)
            results = results.filter(examination__academic_year=year)
        marks = _performance_value(results)
        rows.append([
            teacher.staff_id,
            teacher.full_name,
            teacher.department.name if teacher.department else 'Unassigned',
            subjects.distinct().count(),
            plans.count(),
            plans.filter(status=LessonPlan.Status.APPROVED).count(),
            round(observations.aggregate(average=Avg('rating'))['average'], 1)
            if observations.exists() else 'Not evaluated',
            round(marks['average'], 1) if marks['average'] is not None else 'No results',
        ])
    return _academic_report_response(
        request, 'Teacher Performance Report', headers, rows,
        'Teaching assignments, lesson-plan review, classroom observations and associated student assessment results.',
    )


@role_required('dos')
def subject_performance(request):
    from academics.models import AcademicYear, Subject

    year_id = request.GET.get('academic_year', '').strip()
    year = AcademicYear.objects.filter(pk=year_id).first() if year_id.isdigit() else None
    subjects = Subject.objects.filter(is_active=True).select_related(
        'academic_year', 'teacher'
    ).prefetch_related('departments', 'school_classes')
    if year:
        subjects = subjects.filter(academic_year=year)
    headers = [
        'Subject code', 'Subject', 'Department(s)', 'Class(es)', 'Teacher',
        'Academic year', 'Results recorded', 'Average marks (%)',
    ]
    rows = []
    for subject in subjects:
        summary = _performance_value(subject.results.all())
        rows.append([
            subject.code,
            subject.name,
            subject.department_names,
            subject.school_class_names,
            subject.teacher.display_name if subject.teacher else 'Unassigned',
            subject.academic_year.name,
            summary['entries'],
            round(summary['average'], 1) if summary['average'] is not None else 'No results',
        ])
    return _academic_report_response(
        request, 'Subject Performance Report', headers, rows,
        'Assessment averages and coverage of recorded results for each active subject.',
    )


@role_required('dos')
def department_performance(request):
    from academics.models import AcademicYear, Department
    from examinations.models import Result

    year_id = request.GET.get('academic_year', '').strip()
    year = AcademicYear.objects.filter(pk=year_id).first() if year_id.isdigit() else None
    headers = [
        'Department', 'Teachers', 'Classes', 'Subjects', 'Results recorded',
        'Average marks (%)',
    ]
    rows = []
    for department in Department.objects.all():
        subjects = department.subjects.filter(is_active=True)
        classes = department.classes.all()
        teachers = department.teachers.filter(status='active')
        results = Result.objects.filter(subject__departments=department)
        if year:
            subjects = subjects.filter(academic_year=year)
            classes = classes.filter(academic_year=year)
            results = results.filter(examination__academic_year=year)
        summary = _performance_value(results)
        rows.append([
            department.name,
            teachers.count(),
            classes.count(),
            subjects.distinct().count(),
            summary['entries'],
            round(summary['average'], 1) if summary['average'] is not None else 'No results',
        ])
    return _academic_report_response(
        request, 'Department Performance Report', headers, rows,
        'Department level staffing, class, subject and examination performance summary.',
    )


@role_required('dos')
def syllabus_coverage_report(request):
    from academics.models import AcademicYear, SyllabusCoverage

    year_id = request.GET.get('academic_year', '').strip()
    year = AcademicYear.objects.filter(pk=year_id).first() if year_id.isdigit() else None
    coverage = SyllabusCoverage.objects.select_related(
        'academic_year', 'school_class', 'subject', 'updated_by'
    )
    if year:
        coverage = coverage.filter(academic_year=year)
    headers = [
        'Academic year', 'Term', 'Class', 'Subject', 'Topics completed',
        'Topics planned', 'Completion (%)', 'Last updated',
    ]
    rows = [[
        item.academic_year.name, item.term, item.school_class.name,
        item.subject.name, item.topics_completed, item.topics_planned,
        item.completion_percentage, item.updated_at.strftime('%Y-%m-%d'),
    ] for item in coverage]
    return _academic_report_response(
        request, 'Syllabus Coverage Report', headers, rows,
        'Recorded syllabus progress by academic year, term, class and subject.',
    )


@role_required('dos')
def student_progress(request):
    year_id = request.GET.get('academic_year', '').strip()
    year = AcademicYear.objects.filter(pk=year_id).first() if year_id.isdigit() else None
    results = Result.objects.filter(
        student__status=Student.Status.ACTIVE,
        student__is_archived=False,
    )
    if year:
        results = results.filter(examination__academic_year=year)
    student_rows = results.values(
        'student_id', 'student__student_id', 'student__user__first_name',
        'student__user__last_name', 'student__school_class__name',
    ).annotate(
        average=Avg(ExpressionWrapper(
            F('marks_obtained') * 100.0 / F('total_marks'),
            output_field=FloatField(),
        )),
        assessment_count=Count('pk'),
        highest_mark=Max(ExpressionWrapper(
            F('marks_obtained') * 100.0 / F('total_marks'),
            output_field=FloatField(),
        )),
    ).order_by('-average', 'student__user__last_name')
    headers = [
        'Student ID', 'Student', 'Class', 'Assessments',
        'Average (%)', 'Highest subject score (%)', 'Support status',
    ]
    rows = []
    for student in student_rows:
        average = student['average'] or 0
        rows.append([
            student['student__student_id'],
            f"{student['student__user__first_name']} {student['student__user__last_name']}",
            student['student__school_class__name'] or 'Unassigned',
            student['assessment_count'],
            round(average, 1),
            round(student['highest_mark'] or 0, 1),
            'Needs academic support' if average < 50 else 'On track',
        ])
    return _academic_report_response(
        request, 'Student Academic Progress', headers, rows,
        'Student assessment averages, coverage of recorded assessments and an academic support indicator. The support indicator uses a 50% average threshold.',
    )
