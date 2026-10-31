import json
from datetime import timedelta

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
from finance.services import fee_totals_for_student
from school.generic import RequiredCreateFieldsMixin


class SchoolLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = StyledLoginForm
    redirect_authenticated_user = True


def _month_series(queryset, date_field, value_field='amount', months=6):
    start = timezone.localdate().replace(day=1) - timedelta(days=155)
    rows = (
        queryset.filter(**{f'{date_field}__gte': start})
        .annotate(month=TruncMonth(date_field))
        .values('month')
        .annotate(total=Sum(value_field))
        .order_by('month')
    )
    labels, values = [], []
    for row in rows:
        if row['month']:
            labels.append(row['month'].strftime('%b %Y'))
            values.append(float(row['total'] or 0))
    return labels, values


def _finance_snapshot():
    from finance.models import Fee, Payment

    current_year = None
    try:
        from academics.models import AcademicYear

        current_year = AcademicYear.objects.filter(is_current=True).first()
    except Exception:
        pass

    fees = Fee.objects.all()
    if current_year:
        fees = fees.filter(Q(academic_year=current_year) | Q(academic_year__isnull=True))

    expected = 0
    from students.models import Student

    active_students = Student.objects.filter(status=Student.Status.ACTIVE).count()
    for fee in fees.select_related('school_class'):
        if fee.school_class_id:
            count = Student.objects.filter(
                school_class=fee.school_class, status=Student.Status.ACTIVE
            ).count()
        else:
            count = active_students
        expected += float(fee.amount) * count

    collected = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0
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
            total=Count('students', filter=Q(students__status=Student.Status.ACTIVE))
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
        Student.objects.select_related('user', 'school_class')
        .order_by('-created_at')[:6]
    )
    announcements = Announcement.objects.filter(is_published=True).order_by('-created_at')[:5]

    return {
        'total_students': Student.objects.count(),
        'active_students': Student.objects.filter(status=Student.Status.ACTIVE).count(),
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

    subjects = teacher_subjects(user).prefetch_related('school_classes')
    classes = teacher_classes(user)
    students = Student.objects.filter(
        school_class__in=classes, status=Student.Status.ACTIVE
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
    from students.models import Student

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

    report_cards = Examination.objects.filter(
        results__student=student, is_published=True
    ).select_related('academic_year', 'term').distinct().order_by('-start_date')

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


def _parent_dashboard_context(user):
    from attendance.models import Attendance
    from students.models import Student

    parent = getattr(user, 'parent_profile', None)
    if not parent:
        return {'profile_missing': 'No parent profile is linked to your account.'}

    children = Student.objects.filter(parent=parent).select_related('user', 'school_class')
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
