from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from academics.access import teacher_classes, teacher_subjects
from academics.models import SchoolClass, Subject
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
        ws.append(row)
    for column in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column)
        ws.column_dimensions[column[0].column_letter].width = min(max_length + 4, 40)
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    wb.save(response)
    return response


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


@role_required('teacher', 'accountant')
def reports_index(request):
    context = {'page_title': 'Reports & Exports', 'is_teacher': False}
    if request.user.role == 'teacher':
        classes = teacher_classes(request.user)
        context.update({
            'is_teacher': True,
            'student_count': Student.objects.filter(school_class__in=classes).count(),
            'class_count': classes.count(),
            'subject_count': teacher_subjects(request.user).count(),
        })
    else:
        context.update({
            'student_count': Student.objects.count(),
            'teacher_count': Teacher.objects.count(),
            'class_count': SchoolClass.objects.count(),
            'payment_total': Payment.objects.aggregate(total=Sum('amount'))['total'] or 0,
        })
    return render(request, 'reports/index.html', context)


@role_required('accountant')
def export_students(request, fmt):
    students = Student.objects.select_related('user', 'school_class', 'department')
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


@role_required('teacher', 'student', 'parent', 'accountant')
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


@login_required
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


@role_required('teacher', 'accountant')
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
