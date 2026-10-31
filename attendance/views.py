from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView

from academics.access import teacher_classes, teacher_subjects
from academics.models import SchoolClass, Subject
from accounts.mixins import RoleRequiredMixin, role_required
from students.models import Student

from .models import Attendance


class AttendanceListView(RoleRequiredMixin, ListView):
    model = Attendance
    template_name = 'attendance/list.html'
    context_object_name = 'records'
    paginate_by = 15
    allowed_roles = ('teacher', 'student', 'parent', 'accountant')

    def get_queryset(self):
        user = self.request.user
        qs = Attendance.objects.select_related(
            'student__user', 'school_class', 'subject', 'recorded_by'
        )
        if user.role == 'teacher':
            qs = qs.filter(school_class__in=teacher_classes(user))
        elif user.role == 'student':
            qs = qs.filter(student__user=user)
        elif user.role == 'parent':
            qs = qs.filter(student__parent__user=user)
        q = self.request.GET.get('q', '').strip()
        date = self.request.GET.get('date', '').strip()
        status = self.request.GET.get('status', '').strip()
        class_id = self.request.GET.get('school_class', '').strip()
        if q:
            qs = qs.filter(
                Q(student__user__first_name__icontains=q)
                | Q(student__user__last_name__icontains=q)
                | Q(student__student_id__icontains=q)
            )
        if date:
            qs = qs.filter(date=date)
        if status:
            qs = qs.filter(status=status)
        if class_id:
            qs = qs.filter(school_class_id=class_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classes = SchoolClass.objects.all().order_by('name')
        if self.request.user.role == 'teacher':
            classes = teacher_classes(self.request.user).order_by('name')
        context.update({
            'page_title': 'Attendance Records',
            'status_choices': Attendance.Status.choices,
            'classes': classes,
            'q': self.request.GET.get('q', ''),
            'selected_date': self.request.GET.get('date', ''),
            'selected_status': self.request.GET.get('status', ''),
            'selected_class': self.request.GET.get('school_class', ''),
            'can_record': self.request.user.role in ('teacher', 'admin') or self.request.user.is_superuser,
        })
        return context


@role_required('teacher')
def take_attendance(request):
    user = request.user
    classes = teacher_classes(user) if user.role == 'teacher' else SchoolClass.objects.all()

    selected_class = request.GET.get('school_class') or request.POST.get('school_class')
    selected_date = request.GET.get('date') or request.POST.get('date') or str(timezone.localdate())
    selected_subject = request.GET.get('subject') or request.POST.get('subject') or ''

    school_class = None
    students = Student.objects.none()
    subjects = Subject.objects.none()

    if selected_class:
        school_class = get_object_or_404(classes, pk=selected_class)
        students = Student.objects.filter(
            school_class=school_class, status=Student.Status.ACTIVE
        ).select_related('user').order_by('user__first_name', 'user__last_name')
        subjects = Subject.objects.filter(school_classes=school_class)
        if user.role == 'teacher':
            subjects = subjects.filter(pk__in=teacher_subjects(user))

    if request.method == 'POST' and school_class:
        subject = None
        if selected_subject and selected_subject.isdigit():
            subject_scope = Subject.objects.filter(
                pk=selected_subject, school_classes=school_class
            )
            if user.role == 'teacher':
                subject_scope = subject_scope.filter(pk__in=teacher_subjects(user))
            subject = subject_scope.first()
            if not subject:
                messages.error(request, 'You cannot record attendance for that subject.')
                return redirect('attendance:take')
        saved = 0
        for student in students:
            status = request.POST.get(f'status_{student.pk}')
            if status not in dict(Attendance.Status.choices):
                continue
            remarks = request.POST.get(f'remarks_{student.pk}', '')
            Attendance.objects.update_or_create(
                student=student,
                school_class=school_class,
                subject=subject,
                date=selected_date,
                defaults={
                    'status': status,
                    'remarks': remarks,
                    'recorded_by': user,
                },
            )
            saved += 1
        messages.success(request, f'Attendance saved for {saved} student(s) on {selected_date}.')
        return redirect('attendance:list')

    existing = {}
    if school_class:
        qs = Attendance.objects.filter(
            school_class=school_class, date=selected_date
        )
        if selected_subject and selected_subject.isdigit():
            qs = qs.filter(subject_id=selected_subject)
        else:
            qs = qs.filter(subject__isnull=True)
        existing = {record.student_id: record for record in qs}

    return render(request, 'attendance/take.html', {
        'page_title': 'Record Attendance',
        'classes': classes.order_by('name'),
        'subjects': subjects.order_by('name'),
        'students': students,
        'school_class': school_class,
        'selected_class': str(selected_class or ''),
        'selected_date': selected_date,
        'selected_subject': str(selected_subject or ''),
        'existing': existing,
        'status_choices': Attendance.Status.choices,
    })


@login_required
def attendance_report(request):
    classes = SchoolClass.objects.all().order_by('name')
    if request.user.role == 'teacher':
        classes = teacher_classes(request.user).order_by('name')
    class_id = request.GET.get('school_class', '').strip()
    start = request.GET.get('start_date', '')
    end = request.GET.get('end_date', '')

    records = Attendance.objects.select_related('student__user', 'school_class')
    if request.user.role == 'teacher':
        records = records.filter(
            Q(school_class__subjects__teacher=request.user)
            | Q(school_class__class_teacher=request.user)
        ).distinct()
    elif request.user.role == 'student':
        records = records.filter(student__user=request.user)
    elif request.user.role == 'parent':
        records = records.filter(student__parent__user=request.user)

    if class_id:
        records = records.filter(school_class_id=class_id)
    if start:
        records = records.filter(date__gte=start)
    if end:
        records = records.filter(date__lte=end)

    summary = (
        records.values('student__student_id', 'student__user__first_name',
                       'student__user__last_name', 'school_class__name')
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count('id', filter=Q(status=Attendance.Status.ABSENT)),
            late=Count('id', filter=Q(status=Attendance.Status.LATE)),
            excused=Count('id', filter=Q(status=Attendance.Status.EXCUSED)),
        )
        .order_by('student__user__first_name')
    )
    for row in summary:
        attended = row['present'] + row['late']
        row['percentage'] = round(attended / row['total'] * 100, 1) if row['total'] else 0

    return render(request, 'attendance/report.html', {
        'page_title': 'Attendance Report',
        'classes': classes,
        'summary': summary,
        'selected_class': class_id,
        'start_date': start,
        'end_date': end,
    })
