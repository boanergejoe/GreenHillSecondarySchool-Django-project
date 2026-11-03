from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView

from accounts.forms import BootstrapFormMixin
from accounts.mixins import role_required, user_has_role
from accounts.models import User
from academics.access import teacher_can_access_student, teacher_classes
from academics.models import AcademicYear, Enrollment, SchoolClass
from school.generic import BaseCreateView, BaseDeleteView, BaseListView, BaseUpdateView

from .forms import (
    ParentForm, ReadmissionForm, StudentForm, StudentReadmissionRequestForm,
)
from .models import Parent, ReadmissionRequest, Student
from .services import (
    apply_readmission, archive_student, restore_student,
)


def can_view_student(user, student):
    if student.is_archived and user.role in ('student', 'parent'):
        return False
    if user_has_role(user, ('accountant', 'registrar')):
        return True
    if user.role == 'teacher':
        return teacher_can_access_student(user, student)
    if user.role == 'student':
        return student.user_id == user.id
    if user.role == 'parent':
        return student.parent_id and student.parent.user_id == user.id
    return False


class StudentListView(BaseListView):
    model = Student
    page_title = 'Students'
    allowed_roles = ('teacher', 'accountant', 'registrar')
    search_fields = [
        'student_id', 'user__first_name', 'user__last_name', 'user__email',
        'user__username', 'department__name',
    ]
    columns = [
        ('Student ID', 'student_id'),
        ('Full Name', 'user.display_name'),
        ('Class', 'school_class.name'),
        ('Department', 'department.name'),
        ('Gender', 'get_gender_display'),
        ('Status', 'get_status_display'),
        ('Admitted', 'admission_date'),
    ]
    create_url_name = 'students:student_create'
    edit_url_name = 'students:student_update'
    delete_url_name = 'students:student_delete'
    detail_url_name = 'students:student_detail'
    create_label = 'Register Student'
    create_roles = ('accountant', 'registrar')

    def get_queryset(self):
        qs = Student.objects.filter(is_archived=False).select_related(
            'user', 'school_class', 'department'
        )
        q = self.request.GET.get('q', '').strip()
        class_id = self.request.GET.get('school_class', '').strip()
        status = self.request.GET.get('status', '').strip()
        if self.request.user.role == 'teacher':
            qs = qs.filter(school_class__in=teacher_classes(self.request.user))
        if q:
            qs = qs.filter(
                Q(student_id__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(user__email__icontains=q)
                | Q(user__username__icontains=q)
            )
        if class_id:
            qs = qs.filter(school_class_id=class_id)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classes = SchoolClass.objects.all().order_by('name')
        if self.request.user.role == 'teacher':
            classes = teacher_classes(self.request.user).order_by('name')
        context.update({
            'classes': classes,
            'selected_class': self.request.GET.get('school_class', ''),
            'selected_status': self.request.GET.get('status', ''),
            'status_choices': Student.Status.choices,
            'archived_students_url': reverse_lazy('students:archived_students')
            if self.request.user.role in ('admin', 'registrar')
            or self.request.user.is_superuser else None,
        })
        return context


class StudentCreateView(BaseCreateView):
    model = Student
    form_class = StudentForm
    page_title = 'Register Student'
    success_url = reverse_lazy('students:student_list')
    cancel_url_name = 'students:student_list'
    success_message = 'Student registered successfully.'
    allowed_roles = ('accountant', 'registrar')
    required_field_exclusions = ('department',)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class StudentUpdateView(BaseUpdateView):
    model = Student
    form_class = StudentForm
    page_title = 'Edit Student'
    success_url = reverse_lazy('students:student_list')
    cancel_url_name = 'students:student_list'
    success_message = 'Student record updated successfully.'
    allowed_roles = ('accountant', 'registrar')
    required_field_exclusions = ('department',)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class StudentDeleteView(BaseDeleteView):
    model = Student
    page_title = 'Archive Student'
    success_url = reverse_lazy('students:student_list')
    cancel_url_name = 'students:student_list'
    allowed_roles = ('accountant', 'registrar')

    def form_valid(self, form):
        archive_student(self.object, self.request.user)
        messages.success(self.request, 'Student archived. The record and history can be restored.')
        return redirect(self.success_url)


class StudentDetailView(DetailView):
    model = Student
    template_name = 'students/student_detail.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        student = get_object_or_404(Student, pk=kwargs['pk'])
        if not can_view_student(request.user, student):
            raise PermissionDenied('You cannot view this student record.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Student.objects.select_related(
            'user', 'school_class', 'department', 'parent__user'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        results = student.results.select_related('subject', 'examination')
        if self.request.user.role in ('student', 'parent'):
            results = results.filter(examination__is_published=True)
        context.update({
            'page_title': f'Student - {student.full_name}',
            'results': results[:10],
            'attendance': student.attendance_records.select_related('subject')[:10],
            'payments': student.payments.select_related('fee')[:10],
            'can_view_payments': user_has_role(
                self.request.user, ('accountant',)
            ) or self.request.user.role in ('student', 'parent'),
            'submissions': student.submissions.select_related('assignment')[:10],
            'can_view_medical_data': user_has_role(
                self.request.user, ('accountant',)
            ),
            'attendance_percentage': student.attendance_percentage,
            'enrollments': student.enrollments.select_related(
                'school_class', 'academic_year'
            ).order_by('-enrolled_on'),
            'can_manage_enrollment': user_has_role(
                self.request.user, ('registrar', 'accountant')
            ),
        })
        return context


class ArchivedStudentListView(BaseListView):
    model = Student
    template_name = 'students/archived_list.html'
    context_object_name = 'objects'
    page_title = 'Archived Students'
    allowed_roles = ('registrar',)
    search_fields = [
        'student_id', 'user__first_name', 'user__last_name', 'user__email',
    ]
    columns = [
        ('Student ID', 'student_id'),
        ('Name', 'user.display_name'),
        ('Class', 'school_class.name'),
        ('Archived', 'archived_at'),
    ]

    def get_queryset(self):
        return Student.objects.filter(is_archived=True).select_related(
            'user', 'school_class', 'archived_by'
        )


@login_required
def restore_archived_student(request, pk):
    if request.method != 'POST':
        return redirect('students:archived_students')
    if not user_has_role(request.user, ('registrar',)):
        raise PermissionDenied('You cannot restore student records.')
    student = get_object_or_404(Student, pk=pk, is_archived=True)
    student = restore_student(student)
    messages.success(request, f'{student.full_name} has been restored.')
    return redirect('students:archived_students')


@login_required
def readmit_student(request, pk):
    if not user_has_role(request.user, ('registrar', 'accountant')):
        raise PermissionDenied('You cannot re-admit students.')
    student = get_object_or_404(Student.objects.select_related('user'), pk=pk)
    form = ReadmissionForm(
        request.POST or None,
        initial={'admission_date': timezone.localdate()},
    )
    if request.method == 'POST' and form.is_valid():
        school_class = form.cleaned_data['school_class']
        student = apply_readmission(
            student,
            school_class,
            form.cleaned_data['terms'],
            form.cleaned_data['admission_date'],
        )
        messages.success(
            request,
            f'{student.full_name} was re-admitted to {school_class.name}.',
        )
        return redirect('students:student_detail', pk=student.pk)
    return render(request, 'students/readmit_form.html', {
        'page_title': f'Re-admit {student.full_name}',
        'student': student,
        'form': form,
        'cancel_url': reverse_lazy('students:student_detail', args=[student.pk]),
    })


@login_required
def request_readmission(request):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied('Only students can submit their own re-admission request.')
    with transaction.atomic():
        student = get_object_or_404(
            Student.objects.select_for_update(),
            user=request.user,
            is_archived=False,
        )
        existing_request = student.readmission_requests.filter(
            status=ReadmissionRequest.Status.PENDING
        ).first()
        if existing_request:
            messages.info(
                request,
                'You already have a re-admission request awaiting review.',
            )
            return redirect('accounts:dashboard')

        form = StudentReadmissionRequestForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            readmission_request = form.save(commit=False)
            readmission_request.student = student
            try:
                with transaction.atomic():
                    readmission_request.save()
            except IntegrityError:
                messages.info(
                    request,
                    'A pending re-admission request already exists.',
                )
                return redirect('accounts:dashboard')
            messages.success(
                request,
                'Your re-admission request was sent to the Registrar for review.',
            )
            return redirect('accounts:dashboard')
    return render(request, 'students/readmission_request_form.html', {
        'page_title': 'Request Re-admission',
        'form': form,
        'cancel_url': reverse_lazy('accounts:dashboard'),
    })


@login_required
def readmission_request_list(request):
    if not user_has_role(request.user, ('registrar',)):
        raise PermissionDenied('You cannot review re-admission requests.')
    requests = ReadmissionRequest.objects.select_related(
        'student__user', 'student__school_class', 'school_class', 'reviewed_by'
    ).order_by('status', '-created_at')
    return render(request, 'students/readmission_requests.html', {
        'page_title': 'Re-admission Requests',
        'requests': requests,
    })


@login_required
def review_readmission_request(request, pk):
    if request.method != 'POST':
        return redirect('students:readmission_request_list')
    if not user_has_role(request.user, ('registrar',)):
        raise PermissionDenied('You cannot review re-admission requests.')

    action = request.POST.get('action')
    if action not in ('approve', 'reject'):
        raise PermissionDenied('Choose a valid review action.')
    with transaction.atomic():
        readmission_request = get_object_or_404(
            ReadmissionRequest.objects.select_for_update().select_related(
                'student', 'school_class'
            ),
            pk=pk,
            status=ReadmissionRequest.Status.PENDING,
        )
        if action == 'approve':
            apply_readmission(
                readmission_request.student,
                readmission_request.school_class,
                readmission_request.terms,
            )
            readmission_request.status = ReadmissionRequest.Status.APPROVED
        else:
            readmission_request.status = ReadmissionRequest.Status.REJECTED
        readmission_request.reviewer_note = request.POST.get(
            'reviewer_note', ''
        ).strip()[:2000]
        readmission_request.reviewed_by = request.user
        readmission_request.reviewed_at = timezone.now()
        readmission_request.save(update_fields=[
            'status', 'reviewer_note', 'reviewed_by', 'reviewed_at',
        ])
    messages.success(
        request,
        f'Re-admission request {readmission_request.get_status_display().lower()}.',
    )
    return redirect('students:readmission_request_list')


class ParentListView(BaseListView):
    model = Parent
    page_title = 'Parents / Guardians'
    allowed_roles = ('accountant', 'registrar')
    search_fields = [
        'user__first_name', 'user__last_name', 'user__email', 'user__phone',
    ]
    columns = [
        ('Name', 'user.display_name'),
        ('Relationship', 'get_relationship_display'),
        ('Phone', 'user.phone'),
        ('Email', 'user.email'),
        ('Children', 'children_count'),
    ]
    create_url_name = 'students:parent_create'
    edit_url_name = 'students:parent_update'
    delete_url_name = 'students:parent_delete'
    detail_url_name = 'students:parent_detail'
    create_label = 'Add Parent'
    create_roles = ('accountant', 'registrar')

    def get_queryset(self):
        return Parent.objects.select_related('user').prefetch_related('children')


class ParentCreateView(BaseCreateView):
    model = Parent
    form_class = ParentForm
    page_title = 'Add Parent / Guardian'
    success_url = reverse_lazy('students:parent_list')
    cancel_url_name = 'students:parent_list'
    success_message = 'Parent account created successfully.'
    allowed_roles = ('accountant', 'registrar')


class ParentUpdateView(BaseUpdateView):
    model = Parent
    form_class = ParentForm
    page_title = 'Edit Parent / Guardian'
    success_url = reverse_lazy('students:parent_list')
    cancel_url_name = 'students:parent_list'
    success_message = 'Parent account updated successfully.'
    allowed_roles = ('accountant', 'registrar')


class ParentDeleteView(BaseDeleteView):
    model = Parent
    page_title = 'Delete Parent / Guardian'
    success_url = reverse_lazy('students:parent_list')
    cancel_url_name = 'students:parent_list'
    allowed_roles = ('accountant', 'registrar')

    def form_valid(self, form):
        user = self.object.user
        response = super().form_valid(form)
        if user:
            user.delete()
        return response


class ParentDetailView(DetailView):
    model = Parent
    template_name = 'students/parent_detail.html'
    context_object_name = 'parent'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        parent = get_object_or_404(Parent, pk=kwargs['pk'])
        allowed = user_has_role(request.user, ('accountant', 'registrar')) or (
            request.user.role == 'parent' and parent.user_id == request.user.id
        )
        if not allowed:
            raise PermissionDenied('You cannot view this parent record.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Parent.objects.select_related('user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Parent - {self.object.user.display_name}'
        context['children'] = self.object.children.select_related('user', 'school_class')
        return context


class PromoteForm(BootstrapFormMixin, forms.Form):
    from_class = forms.ModelChoiceField(queryset=SchoolClass.objects.all())
    to_class = forms.ModelChoiceField(queryset=SchoolClass.objects.all())
    academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.all())

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('from_class') == cleaned.get('to_class'):
            raise forms.ValidationError('The destination class must be different.')
        return cleaned


@role_required()
def promote_students(request):
    form = PromoteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        from_class = form.cleaned_data['from_class']
        to_class = form.cleaned_data['to_class']
        count = Student.objects.filter(
            school_class=from_class,
            status=Student.Status.ACTIVE,
            is_archived=False,
        ).update(school_class=to_class)
        messages.success(request, f'{count} student(s) promoted to {to_class.name}.')
        return redirect('students:student_list')
    return render(request, 'students/promote.html', {
        'form': form,
        'page_title': 'Promote Students',
        'cancel_url': '/students/',
    })
