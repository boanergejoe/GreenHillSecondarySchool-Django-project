import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import ProfileForm, StaffForm, StyledLoginForm
from .mixins import RoleRequiredMixin, role_required
from .models import User
from academics.access import teacher_classes, teacher_subjects
from finance.services import exam_eligibility_for_student, fee_totals_for_student
from school.generic import RequiredCreateFieldsMixin


class SchoolLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = StyledLoginForm
    redirect_authenticated_user = True


def _month_series(queryset, date_field, value_field='amount', months=6):
    today = timezone.localdate()
    current_month = today.year * 12 + today.month - 1
    month_dates = []
    for offset in range(months - 1, -1, -1):
        year, month = divmod(current_month - offset, 12)
        month_dates.append(date(year, month + 1, 1))

    rows = (
        queryset.filter(
            **{
                f'{date_field}__gte': month_dates[0],
                f'{date_field}__lt': date(
                    today.year + (today.month == 12),
                    1 if today.month == 12 else today.month + 1,
                    1,
                ),
            }
        )
        .annotate(month=TruncMonth(date_field))
        .values('month')
        .annotate(total=Sum(value_field))
        .order_by('month')
    )
    totals = {}
    for row in rows:
        if row['month']:
            month = row['month']
            totals[(month.year, month.month)] = float(row['total'] or 0)
    labels = [month.strftime('%b %Y') for month in month_dates]
    values = [
        totals.get((month.year, month.month), 0)
        for month in month_dates
    ]
    return labels, values


def _finance_snapshot():
    from finance.models import Fee, Payment
    from academics.models import AcademicYear

    current_year = AcademicYear.objects.filter(is_current=True).first()

    fees = Fee.objects.filter(is_active=True)
    if current_year:
        fees = fees.filter(Q(academic_year=current_year) | Q(academic_year__isnull=True))

    expected = 0
    from students.models import Student

    active_students = Student.objects.filter(
        status=Student.Status.ACTIVE, is_archived=False
    ).count()
    for fee in fees.select_related('school_class'):
        if fee.school_class_id:
            count = Student.objects.filter(
                school_class=fee.school_class,
                status=Student.Status.ACTIVE,
                is_archived=False,
            ).count()
        else:
            count = active_students
        expected += float(fee.amount) * count

    collected = Payment.objects.filter(
        fee__in=fees
    ).aggregate(total=Sum('amount'))['total'] or 0
    collected = float(collected)
    return {
        'expected_fees': expected,
        'collected_fees': collected,
        'outstanding_fees': max(expected - collected, 0),
        'expected_fees_display': f'{expected:,.2f}',
        'collected_fees_display': f'{collected:,.2f}',
        'outstanding_fees_display': f'{max(expected - collected, 0):,.2f}',
    }


def _admin_dashboard_context():
    from academics.models import AcademicYear, SchoolClass, Subject
    from attendance.models import Attendance
    from communications.models import Announcement
    from finance.models import Payment
    from students.models import Student
    from teachers.models import Teacher

    today = timezone.localdate()
    attendance_qs = Attendance.objects.filter(date=today)
    attendance_counts = attendance_qs.aggregate(
        present=Count('id', filter=Q(status=Attendance.Status.PRESENT)),
        absent=Count('id', filter=Q(status=Attendance.Status.ABSENT)),
        late=Count('id', filter=Q(status=Attendance.Status.LATE)),
        excused=Count('id', filter=Q(status=Attendance.Status.EXCUSED)),
    )
    total_attendance = sum(attendance_counts.values()) or 0
    present_total = attendance_counts['present'] + attendance_counts['late']
    attendance_rate = round(present_total / total_attendance * 100, 1) if total_attendance else 0

    by_class = (
        SchoolClass.objects.annotate(
            total=Count('students', filter=Q(
                students__status=Student.Status.ACTIVE,
                students__is_archived=False,
            ))
        )
        .order_by('-total')
        .values('name', 'total')[:8]
    )

    labels, values = _month_series(Payment.objects.all(), 'payment_date')
    if not labels:
        labels = [timezone.localdate().strftime('%b %Y')]
        values = [0]

    recent_payments = (
        Payment.objects.select_related('student__user', 'fee')
        .order_by('-payment_date', '-created_at')[:6]
    )
    recent_students = (
        Student.objects.filter(is_archived=False).select_related('user', 'school_class')
        .order_by('-created_at')[:6]
    )
    announcements = Announcement.objects.filter(is_published=True).order_by('-created_at')[:5]

    return {
        'total_students': Student.objects.filter(is_archived=False).count(),
        'active_students': Student.objects.filter(
            status=Student.Status.ACTIVE, is_archived=False
        ).count(),
        'total_teachers': Teacher.objects.count(),
        'total_classes': SchoolClass.objects.count(),
        'total_subjects': Subject.objects.count(),
        'attendance': attendance_counts,
        'attendance_rate': attendance_rate,
        'attendance_total': total_attendance,
        'current_year': AcademicYear.objects.filter(is_current=True).first(),
        'fee_snapshot': _finance_snapshot(),
        'class_labels': json.dumps([row['name'] for row in by_class]),
        'class_values': json.dumps([row['total'] for row in by_class]),
        'payment_labels': json.dumps(labels),
        'payment_values': json.dumps(values),
        'recent_payments': recent_payments,
        'recent_students': recent_students,
        'announcements': announcements,
    }


def _teacher_dashboard_context(user):
    from academics.access import teacher_subjects
    from assignments.models import Assignment
    from attendance.models import Attendance
    from communications.models import Announcement
    from students.models import Student
    from teachers.models import Teacher

    teacher = getattr(user, 'teacher_profile', None)
    if not teacher:
        return {'profile_missing': 'No teacher profile is linked to your account.'}

    subjects = teacher_subjects(user).select_related(
        'academic_year', 'teacher'
    ).prefetch_related('school_classes')
    classes = teacher_classes(user)
    students = Student.objects.filter(
        school_class__in=classes,
        status=Student.Status.ACTIVE,
        is_archived=False,
    ).select_related('user', 'school_class')

    attendance_qs = Attendance.objects.filter(recorded_by=user)
    counts = attendance_qs.aggregate(
        present=Count('id', filter=Q(status=Attendance.Status.PRESENT)),
        absent=Count('id', filter=Q(status=Attendance.Status.ABSENT)),
        late=Count('id', filter=Q(status=Attendance.Status.LATE)),
        excused=Count('id', filter=Q(status=Attendance.Status.EXCUSED)),
    )
    assignments = Assignment.objects.filter(
        Q(created_by=user)
        | Q(subject__teacher=user)
        | Q(subject__school_classes__class_teacher=user)
        | Q(subject__school_classes__assigned_teachers__user=user)
    ).distinct().order_by('-created_at')[:5]
    announcements = Announcement.objects.filter(
        audience__in=[Announcement.Audience.ALL, Announcement.Audience.TEACHERS],
        is_published=True,
    ).order_by('-created_at')[:5]

    return {
        'teacher': teacher,
        'subjects': subjects,
        'subject_count': subjects.count(),
        'students': students[:10],
        'student_count': students.count(),
        'attendance': counts,
        'attendance_labels': json.dumps(['Present', 'Absent', 'Late', 'Excused']),
        'attendance_values': json.dumps(
            [counts['present'], counts['absent'], counts['late'], counts['excused']]
        ),
        'assignments': assignments,
        'announcements': announcements,
    }


def _student_dashboard_context(user):
    from academics.models import Subject
    from assignments.models import Assignment
    from attendance.models import Attendance
    from communications.models import Announcement
    from examinations.models import Examination
    from students.models import ReadmissionRequest, Student

    student = Student.objects.select_related(
        'school_class', 'department'
    ).filter(user=user).first()
    if not student:
        return {'profile_missing': 'No student profile is linked to your account.'}

    attendance_qs = Attendance.objects.filter(student=student)
    total = attendance_qs.count()
    attended = attendance_qs.filter(
        status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]
    ).count()
    percentage = round(attended / total * 100, 1) if total else 0

    results = student.results.filter(
        examination__is_published=True
    ).select_related('subject', 'examination').order_by(
        '-examination__start_date', 'subject__name'
    )[:12]

    expected, paid, balance = (
        float(value) for value in fee_totals_for_student(student)
    )
    eligibility = exam_eligibility_for_student(student)
    eligibility_progress = (
        min(100, round(float(eligibility['paid'] / eligibility['expected'] * 100)))
        if eligibility['expected'] else 0
    )

    report_cards = Examination.objects.filter(
        results__student=student, is_published=True
    ).select_related('academic_year').distinct().order_by('-start_date')

    subjects = Subject.objects.filter(
        school_classes=student.school_class
    ).select_related('teacher__user').prefetch_related('school_classes')
    assignments = Assignment.objects.filter(
        subject__in=subjects
    ).select_related('subject').order_by('due_date')[:6]
    announcements = Announcement.objects.filter(
        audience__in=[Announcement.Audience.ALL, Announcement.Audience.STUDENTS],
        is_published=True,
    ).order_by('-created_at')[:5]
    latest_readmission_request = student.readmission_requests.order_by(
        '-created_at'
    ).first()

    return {
        'student': student,
        'attendance_total': total,
        'attendance_present': attended,
        'attendance_percentage': percentage,
        'results': results,
        'report_cards': report_cards,
        'subjects': subjects,
        'subject_count': subjects.count(),
        'fee_expected': f'{expected:,.2f}',
        'fee_paid': f'{paid:,.2f}',
        'fee_balance': f'{balance:,.2f}',
        'exam_eligibility': eligibility,
        'exam_eligibility_progress': eligibility_progress,
        'readmission_request': latest_readmission_request,
        'assignments': assignments,
        'announcements': announcements,
        'attendance_labels': json.dumps(['Present', 'Absent', 'Late', 'Excused']),
        'attendance_values': json.dumps([
            attendance_qs.filter(status=Attendance.Status.PRESENT).count(),
            attendance_qs.filter(status=Attendance.Status.ABSENT).count(),
            attendance_qs.filter(status=Attendance.Status.LATE).count(),
            attendance_qs.filter(status=Attendance.Status.EXCUSED).count(),
        ]),
    }


def _registrar_dashboard_context():
    from academics.models import AcademicYear
    from students.models import ReadmissionRequest, Student

    return {
        'registrar_active_count': Student.objects.filter(
            is_archived=False, status=Student.Status.ACTIVE
        ).count(),
        'registrar_archived_count': Student.objects.filter(is_archived=True).count(),
        'registrar_current_year': AcademicYear.objects.filter(
            is_current=True
        ).first(),
        'registrar_recent_students': Student.objects.filter(
            is_archived=False
        ).select_related('user', 'school_class').order_by('-created_at')[:8],
        'registrar_pending_readmissions': ReadmissionRequest.objects.filter(
            status=ReadmissionRequest.Status.PENDING
        ).select_related(
            'student__user', 'student__school_class', 'school_class'
        ).order_by('created_at')[:5],
        'registrar_pending_readmission_count': ReadmissionRequest.objects.filter(
            status=ReadmissionRequest.Status.PENDING
        ).count(),
    }


def _dos_dashboard_context():
    from academics.models import (
        AcademicAuditLog, AcademicYear, LessonPlan, SchoolClass, Subject,
        ExaminationSession, SyllabusCoverage, TeacherAttendance,
    )
    from attendance.models import Attendance
    from examinations.models import Examination, Result
    from django.db.models import Avg, ExpressionWrapper, F, FloatField
    from students.models import Student
    from teachers.models import Teacher
    from .models import User

    current_year = AcademicYear.objects.filter(is_current=True).first()
    examinations = Examination.objects.select_related('academic_year')
    results = Result.objects.all()
    subjects = Subject.objects.filter(is_active=True)
    classes = SchoolClass.objects.all()
    coverage = SyllabusCoverage.objects.all()
    lesson_plans = LessonPlan.objects.select_related(
        'teacher', 'subject', 'school_class'
    )
    if current_year:
        examinations = examinations.filter(academic_year=current_year)
        results = results.filter(examination__academic_year=current_year)
        subjects = subjects.filter(academic_year=current_year)
        classes = classes.filter(academic_year=current_year)
        coverage = coverage.filter(academic_year=current_year)
        lesson_plans = lesson_plans.filter(academic_year=current_year)

    today = timezone.localdate()
    attendance_today = Attendance.objects.filter(date=today)
    teacher_attendance_today = TeacherAttendance.objects.filter(date=today)
    upcoming_examinations = examinations.filter(
        start_date__gte=today
    ).order_by('start_date', 'name')[:6]
    upcoming_sessions = ExaminationSession.objects.filter(
        exam_date__gte=today,
    )
    if current_year:
        upcoming_sessions = upcoming_sessions.filter(
            examination__academic_year=current_year
        )
    upcoming_sessions = upcoming_sessions.select_related(
        'examination', 'school_class', 'subject'
    ).prefetch_related('invigilators').order_by(
        'exam_date', 'start_time'
    )[:6]
    pending_lesson_plans = lesson_plans.filter(
        status=LessonPlan.Status.PENDING
    )
    performance = results.aggregate(
        average=Avg(ExpressionWrapper(
            F('marks_obtained') * 100.0 / F('total_marks'),
            output_field=FloatField(),
        ))
    )['average']
    coverage_records = list(coverage)
    planned_topics = sum(item.topics_planned for item in coverage_records)
    completed_topics = sum(item.topics_completed for item in coverage_records)
    syllabus_completion = (
        round(completed_topics / planned_topics * 100, 1)
        if planned_topics else None
    )
    departmental_performance = list(
        results.values('subject__departments__name').annotate(
            average=Avg(ExpressionWrapper(
                F('marks_obtained') * 100.0 / F('total_marks'),
                output_field=FloatField(),
            ))
        ).order_by('subject__departments__name')
    )
    performance_by_class = list(
        results.values('student__school_class__name').annotate(
            average=Avg(ExpressionWrapper(
                F('marks_obtained') * 100.0 / F('total_marks'),
                output_field=FloatField(),
            ))
        ).order_by('student__school_class__name')
    )
    student_performance = results.filter(
        student__status=Student.Status.ACTIVE,
        student__is_archived=False,
    ).values(
        'student_id', 'student__student_id', 'student__user__first_name',
        'student__user__last_name', 'student__school_class__name',
    ).annotate(
        average=Avg(ExpressionWrapper(
            F('marks_obtained') * 100.0 / F('total_marks'),
            output_field=FloatField(),
        )),
        assessment_count=Count('pk'),
    )
    teacher_activity = list(
        Teacher.objects.filter(status=Teacher.Status.ACTIVE).select_related(
            'user'
        ).prefetch_related('user__teaching_subjects').order_by(
            'user__first_name', 'user__last_name'
        )
    )
    recent_activities = AcademicAuditLog.objects.select_related(
        'actor'
    ).order_by('-created_at')[:8]
    return {
        'dos_current_year': current_year,
        'dos_student_count': Student.objects.filter(
            status=Student.Status.ACTIVE, is_archived=False,
            school_class__in=classes,
        ).count(),
        'dos_teacher_count': Teacher.objects.filter(
            status=Teacher.Status.ACTIVE
        ).count(),
        'dos_teacher_total_count': User.objects.filter(
            role=User.Role.TEACHER, is_active=True
        ).count(),
        'dos_class_count': classes.count(),
        'dos_subject_count': subjects.count(),
        'dos_stream_count': classes.exclude(stream='').values(
            'level', 'stream'
        ).distinct().count(),
        'dos_exam_count': examinations.count(),
        'dos_draft_exam_count': examinations.filter(is_published=False).count(),
        'dos_result_count': results.count(),
        'dos_academic_average': round(performance, 1) if performance is not None else None,
        'dos_syllabus_completion': syllabus_completion,
        'dos_coverage_count': len(coverage_records),
        'dos_planned_topics': planned_topics,
        'dos_completed_topics': completed_topics,
        'dos_pending_report_count': pending_lesson_plans.count(),
        'dos_pending_lesson_plans': pending_lesson_plans.order_by(
            'lesson_date', 'teacher__first_name'
        )[:6],
        'dos_attendance_today_count': attendance_today.count(),
        'dos_teacher_attendance_present_count': teacher_attendance_today.filter(
            status__in=(
                TeacherAttendance.Status.PRESENT,
                TeacherAttendance.Status.LATE,
            )
        ).count(),
        'dos_teacher_attendance_absent_count': teacher_attendance_today.filter(
            status=TeacherAttendance.Status.ABSENT
        ).count(),
        'dos_teacher_attendance_count': teacher_attendance_today.count(),
        'dos_upcoming_examinations': upcoming_examinations,
        'dos_upcoming_exam_sessions': upcoming_sessions,
        'dos_recent_activities': recent_activities,
        'dos_teacher_activity': teacher_activity,
        'dos_department_labels': [
            row['subject__departments__name'] or 'Unassigned'
            for row in departmental_performance
        ],
        'dos_department_values': [
            round(row['average'] or 0, 1) for row in departmental_performance
        ],
        'dos_class_labels': [
            row['student__school_class__name'] or 'Unassigned'
            for row in performance_by_class
        ],
        'dos_class_performance_values': [
            round(row['average'] or 0, 1) for row in performance_by_class
        ],
        'dos_top_performers': student_performance.order_by('-average')[:5],
        'dos_students_needing_support': student_performance.filter(
            average__lt=50
        ).order_by('average')[:5],
    }


def _parent_dashboard_context(user):
    from attendance.models import Attendance
    from students.models import Student

    parent = getattr(user, 'parent_profile', None)
    if not parent:
        return {'profile_missing': 'No parent profile is linked to your account.'}

    children = Student.objects.filter(
        parent=parent, is_archived=False
    ).select_related('user', 'school_class')
    child_rows = []
    for child in children:
        attendance = Attendance.objects.filter(student=child)
        total = attendance.count()
        present = attendance.filter(
            status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]
        ).count()
        _, paid, balance = (
            float(value) for value in fee_totals_for_student(child)
        )
        child_rows.append({
            'student': child,
            'attendance_percentage': round(present / total * 100, 1) if total else 0,
            'balance': f'{balance:,.2f}',
            'paid': f'{paid:,.2f}',
            'results': child.results.filter(
                examination__is_published=True
            ).select_related('subject', 'examination')[:5],
        })

    return {'parent': parent, 'children': child_rows, 'child_count': len(child_rows)}


@login_required
def dashboard(request):
    user = request.user
    context = {'page_title': 'Dashboard'}

    if user.is_super_admin or user.role == User.Role.ACCOUNTANT:
        context.update(_admin_dashboard_context())
        context['dashboard_type'] = 'admin' if user.is_super_admin else 'accountant'
    elif user.role == User.Role.REGISTRAR:
        context.update(_registrar_dashboard_context())
        context['dashboard_type'] = 'registrar'
    elif user.role == User.Role.DOS:
        context.update(_dos_dashboard_context())
        context['dashboard_type'] = 'dos'
    elif user.role == User.Role.TEACHER:
        context.update(_teacher_dashboard_context(user))
        context['dashboard_type'] = 'teacher'
    elif user.role == User.Role.STUDENT:
        context.update(_student_dashboard_context(user))
        context['dashboard_type'] = 'student'
    elif user.role == User.Role.PARENT:
        context.update(_parent_dashboard_context(user))
        context['dashboard_type'] = 'parent'
    else:
        context['dashboard_type'] = 'unknown'

    return render(request, 'dashboard/index.html', context)


@login_required
def profile(request):
    return render(request, 'accounts/profile.html', {'page_title': 'My Profile'})


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Edit Profile'
        context['cancel_url'] = reverse_lazy('accounts:profile')
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Your profile has been updated.')
        return super().form_valid(form)


class StaffListView(RoleRequiredMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 10
    allowed_roles = ()

    def get_queryset(self):
        qs = User.objects.exclude(role=User.Role.STUDENT).exclude(role=User.Role.PARENT)
        q = self.request.GET.get('q', '').strip()
        role = self.request.GET.get('role', '').strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(username__icontains=q)
                | Q(email__icontains=q)
            )
        if role:
            qs = qs.filter(role=role)
        return qs.order_by('first_name', 'last_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Staff Accounts',
            'q': self.request.GET.get('q', ''),
            'selected_role': self.request.GET.get('role', ''),
            'role_choices': [
                (User.Role.ADMIN, 'Super Administrator'),
                (User.Role.TEACHER, 'Teacher / Lecturer'),
                (User.Role.ACCOUNTANT, 'Accountant'),
                (User.Role.REGISTRAR, 'Registrar'),
                (User.Role.DOS, 'Director of Studies (DOS)'),
            ],
        })
        return context


class StaffCreateView(RequiredCreateFieldsMixin, RoleRequiredMixin, CreateView):
    model = User
    form_class = StaffForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')
    allowed_roles = ()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Add Staff Account'
        context['cancel_url'] = self.success_url
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Staff account created successfully.')
        return super().form_valid(form)


class StaffUpdateView(RoleRequiredMixin, UpdateView):
    model = User
    form_class = StaffForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')
    allowed_roles = ()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Edit Staff Account'
        context['cancel_url'] = self.success_url
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Staff account updated successfully.')
        return super().form_valid(form)


class StaffDeleteView(RoleRequiredMixin, DeleteView):
    model = User
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('accounts:user_list')
    allowed_roles = ()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Delete Staff Account'
        context['cancel_url'] = self.success_url
        return context

    def form_valid(self, form):
        if self.object == self.request.user:
            messages.error(self.request, 'You cannot delete your own account.')
            return redirect(self.success_url)
        messages.success(self.request, 'Staff account deleted.')
        return super().form_valid(form)
