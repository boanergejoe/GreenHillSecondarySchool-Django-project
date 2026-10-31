from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from academics.access import (
    teacher_can_access_student, teacher_class_ids, teacher_classes, teacher_subjects,
)
from academics.models import SchoolClass, Subject
from accounts.mixins import role_required, user_has_role
from school.generic import BaseCreateView, BaseDeleteView, BaseListView, BaseUpdateView
from students.models import Student

from .forms import ExaminationForm
from .models import Examination, Result

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
except ImportError:  # pragma: no cover
    colors = None


class ExaminationListView(BaseListView):
    model = Examination
    page_title = 'Examinations'
    allowed_roles = ('teacher', 'accountant')
    search_fields = ['name', 'academic_year__name', 'school_class__name']
    columns = [
        ('Examination', 'name'), ('Type', 'get_exam_type_display'),
        ('Academic Year', 'academic_year.name'), ('Class', 'school_class.name'),
        ('Start', 'start_date'), ('End', 'end_date'), ('Published', 'is_published'),
    ]
    create_url_name = 'examinations:exam_create'
    edit_url_name = 'examinations:exam_update'
    delete_url_name = 'examinations:exam_delete'
    detail_url_name = 'examinations:exam_detail'
    create_label = 'Create Examination'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == 'teacher':
            qs = qs.filter(
                Q(school_class_id__in=teacher_class_ids(self.request.user))
                | Q(school_class__isnull=True)
            ).distinct()
        return qs


class ExaminationCreateView(BaseCreateView):
    model = Examination
    form_class = ExaminationForm
    page_title = 'Create Examination'
    success_url = reverse_lazy('examinations:exam_list')
    cancel_url_name = 'examinations:exam_list'
    success_message = 'Examination created successfully.'


class ExaminationUpdateView(BaseUpdateView):
    model = Examination
    form_class = ExaminationForm
    page_title = 'Edit Examination'
    success_url = reverse_lazy('examinations:exam_list')
    cancel_url_name = 'examinations:exam_list'
    success_message = 'Examination updated successfully.'


class ExaminationDeleteView(BaseDeleteView):
    model = Examination
    page_title = 'Delete Examination'
    success_url = reverse_lazy('examinations:exam_list')
    cancel_url_name = 'examinations:exam_list'


@login_required
def exam_detail(request, pk):
    exam = get_object_or_404(
        Examination.objects.select_related('academic_year', 'term', 'school_class'), pk=pk
    )
    if (
        request.user.role == 'teacher'
        and exam.school_class_id
        and not teacher_classes(request.user).filter(pk=exam.school_class_id).exists()
    ):
        raise PermissionDenied('You cannot view this examination.')

    subjects = Subject.objects.filter(academic_year=exam.academic_year)
    if exam.school_class_id:
        subjects = subjects.filter(school_class=exam.school_class)
    if request.user.role == 'teacher':
        subjects = subjects.filter(
            Q(teacher=request.user) | Q(school_class__class_teacher=request.user)
        ).distinct()
    subject_rows = subjects.annotate(result_count=Count('results')).select_related(
        'school_class', 'teacher'
    )
    results_qs = exam.results.select_related('student__user', 'subject')
    if request.user.role == 'teacher':
        results_qs = results_qs.filter(subject__in=subjects)
    results = results_qs[:20]
    return render(request, 'examinations/exam_detail.html', {
        'page_title': f'Examination - {exam.name}',
        'exam': exam,
        'subjects': subject_rows,
        'results': results,
        'result_count': results_qs.count(),
    })


@role_required('teacher')
def enter_results(request, pk):
    exam = get_object_or_404(Examination, pk=pk)
    subjects = Subject.objects.filter(academic_year=exam.academic_year)
    if exam.school_class_id:
        subjects = subjects.filter(school_class=exam.school_class)
    if request.user.role == 'teacher':
        subjects = subjects.filter(
            Q(teacher=request.user) | Q(school_class__class_teacher=request.user)
        ).distinct()

    subject_id = request.GET.get('subject') or request.POST.get('subject')
    subject = None
    students = Student.objects.none()
    if subject_id:
        subject = get_object_or_404(subjects, pk=subject_id)
        students = Student.objects.filter(
            school_class=subject.school_class, status=Student.Status.ACTIVE
        ).select_related('user').order_by('user__first_name', 'user__last_name')

    if request.method == 'POST' and subject:
        saved = 0
        for student in students:
            raw = request.POST.get(f'marks_{student.pk}', '').strip()
            if raw == '':
                continue
            try:
                marks = Decimal(raw)
            except InvalidOperation:
                messages.error(request, f'Invalid mark for {student.full_name}.')
                continue
            if marks < 0 or marks > exam.total_marks:
                messages.error(
                    request, f'Marks for {student.full_name} must be between 0 and {exam.total_marks}.'
                )
                continue
            Result.objects.update_or_create(
                student=student,
                examination=exam,
                subject=subject,
                defaults={
                    'marks_obtained': marks,
                    'total_marks': exam.total_marks,
                    'entered_by': request.user,
                },
            )
            saved += 1
        messages.success(request, f'{saved} result(s) saved for {subject.name}.')
        return redirect('examinations:exam_detail', pk=exam.pk)

    existing = {}
    if subject:
        existing = {
            result.student_id: result
            for result in Result.objects.filter(examination=exam, subject=subject)
        }

    return render(request, 'examinations/enter_results.html', {
        'page_title': f'Enter Results - {exam.name}',
        'exam': exam,
        'subjects': subjects.order_by('name'),
        'subject': subject,
        'students': students,
        'existing': existing,
        'selected_subject': str(subject_id or ''),
    })


@login_required
def result_list(request):
    user = request.user
    qs = Result.objects.select_related(
        'student__user', 'examination', 'subject', 'subject__school_class'
    )
    if user.role == 'student':
        qs = qs.filter(student__user=user)
    elif user.role == 'parent':
        qs = qs.filter(student__parent__user=user)
    elif user.role == 'teacher':
        qs = qs.filter(
            Q(subject__teacher=user) | Q(subject__school_class__class_teacher=user)
        ).distinct()

    exam_id = request.GET.get('examination', '').strip()
    class_id = request.GET.get('school_class', '').strip()
    subject_id = request.GET.get('subject', '').strip()
    q = request.GET.get('q', '').strip()
    if exam_id:
        qs = qs.filter(examination_id=exam_id)
    if class_id:
        qs = qs.filter(subject__school_class_id=class_id)
    if subject_id:
        qs = qs.filter(subject_id=subject_id)
    if q:
        qs = qs.filter(
            Q(student__user__first_name__icontains=q)
            | Q(student__user__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
        )

    examinations = Examination.objects.select_related('academic_year').all()
    classes = SchoolClass.objects.all()
    subjects = Subject.objects.select_related('school_class').all()
    if user.role == 'teacher':
        classes = teacher_classes(user).order_by('name')
        subjects = teacher_subjects(user).select_related('school_class').order_by('name')
        examinations = Examination.objects.filter(
            Q(school_class__in=classes) | Q(school_class__isnull=True)
        ).select_related('academic_year').distinct()

    return render(request, 'examinations/result_list.html', {
        'page_title': 'Examination Results',
        'results': qs.order_by('-examination__start_date', 'student__user__first_name'),
        'examinations': examinations,
        'classes': classes,
        'subjects': subjects,
        'selected_exam': exam_id,
        'selected_class': class_id,
        'selected_subject': subject_id,
        'q': q,
    })


def _report_card_context(student, exam):
    results = Result.objects.filter(student=student, examination=exam).select_related(
        'subject'
    ).order_by('subject__name')
    total_obtained = results.aggregate(total=Sum('marks_obtained'))['total'] or Decimal('0')
    total_marks = results.aggregate(total=Sum('total_marks'))['total'] or Decimal('0')
    has_results = total_marks > 0
    if has_results:
        percentage = round(float(total_obtained) / float(total_marks) * 100, 1)
        grade = Result.compute_grade(percentage)
        performance_remark = Result.remark_for_percentage(percentage)
    else:
        percentage = 0.0
        grade = '-'
        performance_remark = 'No results recorded'
    return {
        'student': student,
        'exam': exam,
        'results': results,
        'has_results': has_results,
        'result_count': results.count(),
        'total_obtained': total_obtained,
        'total_marks': total_marks,
        'percentage': percentage,
        'grade': grade,
        'performance_remark': performance_remark,
        'generated_at': timezone.now(),
    }


def _can_access_report_card(user, student):
    if user_has_role(user, ('accountant',)):
        return True
    if user.role == 'teacher':
        return teacher_can_access_student(user, student)
    if user.role == 'student':
        return student.user_id == user.id
    if user.role == 'parent':
        return bool(student.parent_id and student.parent.user_id == user.id)
    return False


@login_required
def report_card(request, student_id, exam_id):
    student = get_object_or_404(
        Student.objects.select_related('user', 'school_class__department'), pk=student_id
    )
    exam = get_object_or_404(
        Examination.objects.select_related('academic_year', 'term'), pk=exam_id
    )
    if not _can_access_report_card(request.user, student):
        raise PermissionDenied('You cannot view this report card.')
    context = _report_card_context(student, exam)
    context['page_title'] = f'Report Card - {student.full_name}'
    return render(request, 'examinations/report_card.html', context)


@login_required
def report_card_pdf(request, student_id, exam_id):
    if colors is None:
        messages.error(request, 'PDF generation requires the reportlab package.')
        return redirect('examinations:report_card', student_id=student_id, exam_id=exam_id)

    student = get_object_or_404(
        Student.objects.select_related('user', 'school_class__department'), pk=student_id
    )
    exam = get_object_or_404(
        Examination.objects.select_related('academic_year', 'term'), pk=exam_id
    )
    if not _can_access_report_card(request.user, student):
        raise PermissionDenied('You cannot download this report card.')

    context = _report_card_context(student, exam)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="report-card-{student.student_id}-{exam.pk}.pdf"'
    )
    doc = SimpleDocTemplate(
        response, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )

    green = colors.HexColor('#1c5a35')
    gold = colors.HexColor('#c9a227')
    pale = colors.HexColor('#f2f8f4')
    line = colors.HexColor('#d6e4da')
    muted = colors.HexColor('#4b5563')
    styles = getSampleStyleSheet()
    school_style = ParagraphStyle(
        'SchoolName', parent=styles['Title'], fontName='Helvetica-Bold',
        fontSize=17, leading=20, textColor=green, alignment=0, spaceAfter=2,
    )
    motto_style = ParagraphStyle(
        'Motto', parent=styles['Normal'], fontName='Helvetica-Oblique',
        fontSize=8.5, leading=11, textColor=gold,
    )
    small_style = ParagraphStyle(
        'Small', parent=styles['Normal'], fontSize=7.8, leading=10.5, textColor=muted,
    )
    value_style = ParagraphStyle(
        'Value', parent=styles['Normal'], fontSize=8.2, leading=10.5,
    )
    band_style = ParagraphStyle(
        'Band', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=11.5, leading=14, textColor=colors.white, alignment=1,
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=9, leading=11, textColor=green, spaceBefore=3, spaceAfter=4,
    )

    logo_path = finders.find('images/logo.jpeg')
    if logo_path:
        logo = Image(logo_path, width=26 * mm, height=26 * mm)
    else:
        logo = Paragraph('GH', ParagraphStyle(
            'LogoFallback', parent=styles['Title'], fontSize=26, textColor=green,
        ))

    school_details = [
        Paragraph(escape(settings.SCHOOL_NAME), school_style),
        Paragraph(escape(settings.SCHOOL_MOTTO), motto_style),
        Paragraph(escape(settings.SCHOOL_ADDRESS), small_style),
        Paragraph(
            f'{escape(settings.SCHOOL_PHONE)} &nbsp;|&nbsp; '
            f'{escape(settings.SCHOOL_EMAIL)}',
            small_style,
        ),
    ]
    header = Table([[logo, school_details]], colWidths=[31 * mm, 143 * mm])
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    accent = Table([['']], colWidths=[174 * mm], rowHeights=[1.6 * mm])
    accent.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), green),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    title_band = Table(
        [[Paragraph('OFFICIAL STUDENT REPORT CARD', band_style)]],
        colWidths=[174 * mm],
    )
    title_band.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), green),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))

    department = (
        student.school_class.department.name
        if student.school_class and student.school_class.department_id else '-'
    )
    info_data = [
        ['Student', student.full_name, 'Student ID', student.student_id],
        ['Class', student.school_class.name if student.school_class else '-',
         'Department', department],
        ['Academic Year', exam.academic_year.name, 'Term',
         exam.term.name if exam.term_id else '-'],
        ['Examination', exam.name, 'Generated',
         context['generated_at'].strftime('%d %b %Y')],
    ]
    info_table_data = []
    for row in info_data:
        info_table_data.append([
            Paragraph(f'<b>{escape(row[0])}</b>', value_style),
            Paragraph(escape(str(row[1])), value_style),
            Paragraph(f'<b>{escape(row[2])}</b>', value_style),
            Paragraph(escape(str(row[3])), value_style),
        ])
    info_table = Table(info_table_data, colWidths=[27 * mm, 61 * mm, 28 * mm, 58 * mm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), pale),
        ('BACKGROUND', (2, 0), (2, -1), pale),
        ('TEXTCOLOR', (0, 0), (-1, -1), muted),
        ('GRID', (0, 0), (-1, -1), 0.4, line),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    result_data = [[
        Paragraph('<b>Subject</b>', value_style),
        Paragraph('<b>Marks</b>', value_style),
        Paragraph('<b>Total</b>', value_style),
        Paragraph('<b>Percentage</b>', value_style),
        Paragraph('<b>Grade</b>', value_style),
        Paragraph('<b>Remarks</b>', value_style),
    ]]
    for result in context['results']:
        result_data.append([
            Paragraph(escape(result.subject.name), value_style),
            Paragraph(f'{float(result.marks_obtained):.1f}', value_style),
            Paragraph(f'{float(result.total_marks):.1f}', value_style),
            Paragraph(f'{float(result.percentage):.1f}%', value_style),
            Paragraph(f'<b>{escape(result.grade)}</b>', value_style),
            Paragraph(escape(result.performance_remark), value_style),
        ])
    if len(result_data) == 1:
        result_data.append([
            Paragraph('No results recorded for this examination.', value_style),
            '', '', '', '', '',
        ])
    result_table = Table(
        result_data, colWidths=[48 * mm, 20 * mm, 18 * mm, 28 * mm, 18 * mm, 42 * mm],
        repeatRows=1,
    )
    result_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, gold),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, pale]),
        ('GRID', (0, 0), (-1, -1), 0.4, line),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))

    summary = Table([
        [Paragraph('Total Obtained', small_style), Paragraph('Total Marks', small_style),
         Paragraph('Percentage', small_style), Paragraph('Final Grade', small_style)],
        [Paragraph(f'<b>{context["total_obtained"]:g}</b>', value_style),
         Paragraph(f'<b>{context["total_marks"]:g}</b>', value_style),
         Paragraph(f'<b>{context["percentage"]}%</b>', value_style),
         Paragraph(f'<b>{context["grade"]}</b>', ParagraphStyle(
             'GradeValue', parent=value_style, fontSize=12, textColor=green,
         ))],
    ], colWidths=[43.5 * mm] * 4)
    summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), pale),
        ('BOX', (0, 0), (-1, -1), 0.5, line),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, line),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))

    grade_key = Table([
        [Paragraph('<b>Grading Scale</b>', value_style), 'A 80-100', 'B 70-79',
         'C 60-69', 'D 50-59', 'E 40-49', 'F Below 40'],
    ], colWidths=[33 * mm] + [23.5 * mm] * 6)
    grade_key.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), pale),
        ('GRID', (0, 0), (-1, -1), 0.4, line),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))

    signatures = Table(
        [['', '', ''], ['Class Teacher', 'Principal', 'Parent / Guardian']],
        colWidths=[58 * mm] * 3,
        rowHeights=[15 * mm, 6 * mm],
    )
    signatures.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 0.6, muted),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('TEXTCOLOR', (0, 1), (-1, 1), muted),
        ('VALIGN', (0, 1), (-1, 1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    story = [
        header,
        Spacer(1, 3),
        accent,
        Spacer(1, 5),
        title_band,
        Spacer(1, 7),
        Paragraph(
            f'{escape(exam.name)} &middot; {escape(exam.academic_year.name)}',
            section_style,
        ),
        info_table,
        Spacer(1, 10),
        Paragraph('Academic Performance', section_style),
        result_table,
        Spacer(1, 8),
        summary,
        Spacer(1, 7),
        grade_key,
        Spacer(1, 14),
        signatures,
        Spacer(1, 8),
        Paragraph(
            f'Generated on {context["generated_at"].strftime("%d %b %Y %H:%M")} '
            f'&middot; {escape(settings.SCHOOL_NAME)} &middot; '
            'This is a computer-generated report card.',
            small_style,
        ),
    ]
    doc.build(story)
    return response


class ResultDeleteView(BaseDeleteView):
    model = Result
    page_title = 'Delete Result'
    success_url = reverse_lazy('examinations:result_list')
    cancel_url_name = 'examinations:result_list'
