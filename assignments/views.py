from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView

from academics.access import teacher_can_manage_assignment
from academics.models import Subject
from accounts.mixins import user_has_role
from school.generic import BaseCreateView, BaseDeleteView, BaseUpdateView, mark_required_fields
from students.models import Student

from .forms import AssignmentForm, ReviewSubmissionForm, SubmissionForm
from .models import Assignment, Submission


class AssignmentListView(ListView):
    model = Assignment
    template_name = 'assignments/list.html'
    context_object_name = 'assignments'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        qs = Assignment.objects.select_related(
            'subject', 'subject__school_class', 'created_by'
        )
        if user.role == 'teacher':
            qs = qs.filter(
                Q(created_by=user)
                | Q(subject__teacher=user)
                | Q(subject__school_class__class_teacher=user)
            ).distinct()
        elif user.role == 'student':
            student = getattr(user, 'student_profile', None)
            if student and student.school_class_id:
                qs = qs.filter(
                    subject__school_class_id=student.school_class_id, is_published=True
                )
            else:
                qs = qs.none()
        elif user.role == 'parent':
            child_classes = Student.objects.filter(
                parent__user=user
            ).values_list('school_class_id', flat=True)
            qs = qs.filter(subject__school_class_id__in=child_classes, is_published=True)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(subject__name__icontains=q))
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Assignments & Materials',
            'q': self.request.GET.get('q', ''),
            'can_create': self.request.user.role in ('teacher', 'admin') or self.request.user.is_superuser,
        })
        return context


class AssignmentCreateView(BaseCreateView):
    model = Assignment
    form_class = AssignmentForm
    page_title = 'Create Assignment'
    success_url = reverse_lazy('assignments:list')
    cancel_url_name = 'assignments:list'
    success_message = 'Assignment created successfully.'
    allowed_roles = ('teacher',)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class AssignmentUpdateView(BaseUpdateView):
    model = Assignment
    form_class = AssignmentForm
    page_title = 'Edit Assignment'
    success_url = reverse_lazy('assignments:list')
    cancel_url_name = 'assignments:list'
    success_message = 'Assignment updated successfully.'
    allowed_roles = ('teacher',)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == 'teacher':
            qs = qs.filter(created_by=self.request.user)
        return qs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class AssignmentDeleteView(BaseDeleteView):
    model = Assignment
    page_title = 'Delete Assignment'
    success_url = reverse_lazy('assignments:list')
    cancel_url_name = 'assignments:list'
    allowed_roles = ('teacher',)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == 'teacher':
            qs = qs.filter(created_by=self.request.user)
        return qs


@login_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(
        Assignment.objects.select_related(
            'subject__school_class', 'subject__teacher', 'created_by'
        ),
        pk=pk,
    )
    user = request.user
    student = getattr(user, 'student_profile', None)
    submission = None
    if student:
        submission = Submission.objects.filter(
            assignment=assignment, student=student
        ).first()

    can_manage = user_has_role(user, ())
    if user.role == 'teacher':
        can_manage = teacher_can_manage_assignment(user, assignment)
        if not can_manage:
            raise PermissionDenied('You cannot view this assignment.')
    elif user.role == 'student':
        if not student or assignment.subject.school_class_id != student.school_class_id:
            raise PermissionDenied('You cannot view this assignment.')
    elif user.role == 'parent':
        child_classes = Student.objects.filter(parent__user=user).values_list(
            'school_class_id', flat=True
        )
        if assignment.subject.school_class_id not in child_classes:
            raise PermissionDenied('You cannot view this assignment.')
    elif not can_manage:
        raise PermissionDenied('You cannot view this assignment.')

    submissions = assignment.submissions.select_related('student__user') if can_manage else []

    return render(request, 'assignments/detail.html', {
        'page_title': assignment.title,
        'assignment': assignment,
        'submission': submission,
        'submissions': submissions,
        'can_manage': can_manage,
        'is_student': user.role == 'student',
        'is_overdue': assignment.is_overdue,
    })


@login_required
def submit_assignment(request, pk):
    if request.user.role != 'student':
        raise PermissionDenied('Only students can submit assignments.')
    assignment = get_object_or_404(Assignment, pk=pk)
    student = getattr(request.user, 'student_profile', None)
    if not student or assignment.subject.school_class_id != student.school_class_id:
        raise PermissionDenied('This assignment is not available to you.')

    submission = Submission.objects.filter(assignment=assignment, student=student).first()
    form = SubmissionForm(request.POST or None, request.FILES or None, instance=submission)
    mark_required_fields(form)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.assignment = assignment
        obj.student = student
        if assignment.is_overdue:
            obj.status = Submission.Status.LATE
        else:
            obj.status = Submission.Status.SUBMITTED
        obj.save()
        messages.success(request, 'Assignment submitted successfully.')
        return redirect('assignments:detail', pk=assignment.pk)

    return render(request, 'assignments/submit.html', {
        'page_title': f'Submit - {assignment.title}',
        'assignment': assignment,
        'form': form,
        'submission': submission,
    })


@login_required
def review_submission(request, pk):
    submission = get_object_or_404(
        Submission.objects.select_related(
            'assignment__subject__school_class', 'student__user'
        ),
        pk=pk,
    )
    user = request.user
    can_review = user_has_role(user, ())
    if user.role == 'teacher':
        can_review = teacher_can_manage_assignment(user, submission.assignment)
    if not can_review:
        raise PermissionDenied('You cannot review this submission.')

    form = ReviewSubmissionForm(request.POST or None, instance=submission)
    mark_required_fields(form)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.reviewed_by = user
        obj.save()
        messages.success(request, 'Submission reviewed successfully.')
        return redirect('assignments:detail', pk=submission.assignment_id)

    return render(request, 'assignments/review.html', {
        'page_title': f'Review - {submission.student.full_name}',
        'form': form,
        'submission': submission,
    })
