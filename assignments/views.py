from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView

from academics.access import teacher_can_manage_assignment, teacher_subjects
from academics.models import Subject
from accounts.mixins import user_has_role
from school.generic import BaseCreateView, BaseDeleteView, BaseUpdateView, mark_required_fields
from students.models import Student

from school.ai import (
    AIServiceError, evaluate_written_submission, generate_multiple_choice_questions,
)

from .forms import (
    AssignmentForm, QuizGenerateForm, ReviewSubmissionForm, SubmissionForm,
)
from .models import Assignment, Quiz, QuizAttempt, QuizQuestion, Submission


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
            'subject', 'created_by'
        ).prefetch_related('subject__school_classes')
        if user.role == 'teacher':
            qs = qs.filter(
                Q(created_by=user)
                | Q(subject__teacher=user)
                | Q(subject__school_classes__class_teacher=user)
                | Q(subject__school_classes__assigned_teachers__user=user)
            ).distinct()
        elif user.role == 'student':
            student = getattr(user, 'student_profile', None)
            if student and student.school_class_id:
                qs = qs.filter(
                    subject__school_classes=student.school_class, is_published=True
                )
            else:
                qs = qs.none()
        elif user.role == 'parent':
            child_classes = Student.objects.filter(
                parent__user=user
            ).values_list('school_class_id', flat=True)
            qs = qs.filter(
                subject__school_classes__in=child_classes, is_published=True
            )
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
            'subject__teacher', 'created_by'
        ).prefetch_related('subject__school_classes'),
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
        if (
            not student
            or not assignment.subject.school_classes.filter(
                pk=student.school_class_id
            ).exists()
        ):
            raise PermissionDenied('You cannot view this assignment.')
    elif user.role == 'parent':
        child_classes = Student.objects.filter(parent__user=user).values_list(
            'school_class_id', flat=True
        )
        if not assignment.subject.school_classes.filter(
            pk__in=child_classes
        ).exists():
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
    assignment = get_object_or_404(
        Assignment.objects.prefetch_related('subject__school_classes'), pk=pk
    )
    student = getattr(request.user, 'student_profile', None)
    if (
        not student
        or not assignment.subject.school_classes.filter(
            pk=student.school_class_id
        ).exists()
    ):
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
            'assignment__subject', 'student__user'
        ).prefetch_related('assignment__subject__school_classes'),
        pk=pk,
    )
    user = request.user
    can_review = user_has_role(user, ())
    if user.role == 'teacher':
        can_review = teacher_can_manage_assignment(user, submission.assignment)
    if not can_review:
        raise PermissionDenied('You cannot review this submission.')

    suggested_grade = False
    if request.method == 'POST' and 'ai_suggest' in request.POST:
        if not submission.comment.strip():
            messages.error(
                request,
                'AI suggestions require a text response in the student submission.',
            )
        else:
            try:
                score, feedback = evaluate_written_submission(
                    submission.assignment, submission.comment
                )
            except AIServiceError as exc:
                messages.error(request, str(exc))
            else:
                form = ReviewSubmissionForm(instance=submission, initial={
                    'score': score,
                    'feedback': feedback,
                    'status': Submission.Status.REVIEWED,
                })
                suggested_grade = True
        if not suggested_grade:
            form = ReviewSubmissionForm(instance=submission)
    else:
        form = ReviewSubmissionForm(
            request.POST or None, instance=submission
        )
    mark_required_fields(form)
    if (
        request.method == 'POST'
        and 'ai_suggest' not in request.POST
        and form.is_valid()
    ):
        obj = form.save(commit=False)
        obj.reviewed_by = user
        obj.save()
        messages.success(request, 'Submission reviewed successfully.')
        return redirect('assignments:detail', pk=submission.assignment_id)

    return render(request, 'assignments/review.html', {
        'page_title': f'Review - {submission.student.full_name}',
        'form': form,
        'submission': submission,
        'suggested_grade': suggested_grade,
    })


def _quiz_manager_can_access(user, quiz):
    return (
        user.is_superuser
        or user.role == 'admin'
        or (
            user.role == 'teacher'
            and (
                quiz.created_by_id == user.pk
                or quiz.subject.teacher_id == user.pk
                or quiz.subject.school_classes.filter(class_teacher_id=user.pk).exists()
                or quiz.subject.school_classes.filter(
                    assigned_teachers__user=user
                ).exists()
            )
        )
    )


@login_required
def quiz_list(request):
    user = request.user
    quizzes = Quiz.objects.select_related('subject', 'created_by').prefetch_related(
        'subject__school_classes', 'questions'
    )
    if user.role == 'student':
        student = getattr(user, 'student_profile', None)
        if student and student.school_class_id:
            quizzes = quizzes.filter(
                subject__school_classes=student.school_class, is_published=True
            )
        else:
            quizzes = quizzes.none()
    elif user.role == 'parent':
        child_classes = Student.objects.filter(
            parent__user=user
        ).values_list('school_class_id', flat=True)
        quizzes = quizzes.filter(
            subject__school_classes__in=child_classes, is_published=True
        )
    elif user.role == 'teacher':
        quizzes = quizzes.filter(subject__in=teacher_subjects(user))
    elif not (user.is_superuser or user.role == 'admin'):
        quizzes = quizzes.none()
    return render(request, 'assignments/quiz_list.html', {
        'page_title': 'Quizzes',
        'quizzes': quizzes.distinct(),
        'can_create': user.role in ('teacher', 'admin') or user.is_superuser,
    })


@login_required
def quiz_create(request):
    if request.user.role not in ('teacher', 'admin') and not request.user.is_superuser:
        raise PermissionDenied('You cannot create quizzes.')
    form = QuizGenerateForm(
        request.POST or None,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            generated = generate_multiple_choice_questions(
                form.cleaned_data['subject'].name,
                form.cleaned_data['topic'],
                form.cleaned_data['question_count'],
            )
        except AIServiceError as exc:
            messages.error(request, str(exc))
        else:
            with transaction.atomic():
                quiz = Quiz.objects.create(
                    subject=form.cleaned_data['subject'],
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data['description'],
                    created_by=request.user,
                    is_published=False,
                )
                QuizQuestion.objects.bulk_create([
                    QuizQuestion(
                        quiz=quiz,
                        prompt=item['prompt'],
                        option_a=item['options'][0],
                        option_b=item['options'][1],
                        option_c=item['options'][2],
                        option_d=item['options'][3],
                        correct_option=item['answer'],
                        position=index,
                    )
                    for index, item in enumerate(generated, start=1)
                ])
            messages.success(
                request,
                'Quiz generated. Review the questions before sharing them with students.',
            )
            return redirect('assignments:quiz_detail', pk=quiz.pk)
    return render(request, 'assignments/quiz_create.html', {
        'page_title': 'Generate Multiple-Choice Quiz',
        'form': form,
    })


@login_required
def quiz_detail(request, pk):
    quiz = get_object_or_404(
        Quiz.objects.select_related('subject', 'created_by').prefetch_related('questions'),
        pk=pk,
    )
    user = request.user
    is_manager = _quiz_manager_can_access(user, quiz)
    student = getattr(user, 'student_profile', None)
    is_student = user.role == 'student'
    if is_student:
        if (
            not quiz.is_published
            or not student
            or not student.school_class_id
            or not quiz.subject.school_classes.filter(pk=student.school_class_id).exists()
        ):
            raise PermissionDenied('This quiz is not available to you.')
    elif user.role == 'parent':
        child_classes = Student.objects.filter(
            parent__user=user
        ).values_list('school_class_id', flat=True)
        if not quiz.is_published or not quiz.subject.school_classes.filter(
            pk__in=child_classes
        ).exists():
            raise PermissionDenied('This quiz is not available to you.')
    elif not is_manager:
        raise PermissionDenied('You cannot view this quiz.')

    attempt = None
    if is_student:
        attempt = QuizAttempt.objects.filter(quiz=quiz, student=student).first()
    return render(request, 'assignments/quiz_detail.html', {
        'page_title': quiz.title,
        'quiz': quiz,
        'questions': quiz.questions.all(),
        'attempt': attempt,
        'is_student': is_student,
        'can_manage': is_manager,
    })


@login_required
def quiz_attempt(request, pk):
    if request.user.role != 'student':
        raise PermissionDenied('Only students can take quizzes.')
    quiz = get_object_or_404(
        Quiz.objects.select_related('subject').prefetch_related('questions'),
        pk=pk,
        is_published=True,
    )
    student = getattr(request.user, 'student_profile', None)
    if (
        not student
        or not student.school_class_id
        or not quiz.subject.school_classes.filter(pk=student.school_class_id).exists()
    ):
        raise PermissionDenied('This quiz is not available to you.')

    if QuizAttempt.objects.filter(quiz=quiz, student=student).exists():
        messages.info(request, 'You have already submitted this quiz.')
        return redirect('assignments:quiz_detail', pk=quiz.pk)

    questions = list(quiz.questions.all())
    if request.method == 'POST':
        answers = {}
        errors = []
        for question in questions:
            raw_answer = request.POST.get(f'question_{question.pk}', '')
            try:
                answer = int(raw_answer)
            except (TypeError, ValueError):
                errors.append('Answer every question before submitting.')
                continue
            if answer not in range(4):
                errors.append('One or more answers are invalid.')
            else:
                answers[str(question.pk)] = answer

        if not questions:
            errors.append('This quiz has no questions and cannot be submitted.')
        if errors:
            for error in dict.fromkeys(errors):
                messages.error(request, error)
        else:
            score = sum(
                answers[str(question.pk)] == question.correct_option
                for question in questions
            )
            attempt, created = QuizAttempt.objects.get_or_create(
                quiz=quiz,
                student=student,
                defaults={'answers': answers, 'score': score},
            )
            if created:
                messages.success(request, 'Your quiz was automatically graded.')
            else:
                messages.info(request, 'You have already submitted this quiz.')
            return redirect('assignments:quiz_detail', pk=quiz.pk)

    return render(request, 'assignments/quiz_attempt.html', {
        'page_title': f'Take quiz: {quiz.title}',
        'quiz': quiz,
        'questions': questions,
    })


@login_required
def quiz_publish(request, pk):
    if request.method != 'POST':
        raise PermissionDenied('Use the publish action to publish a quiz.')
    quiz = get_object_or_404(
        Quiz.objects.select_related('subject', 'created_by'), pk=pk
    )
    if not _quiz_manager_can_access(request.user, quiz):
        raise PermissionDenied('You cannot publish this quiz.')
    if not quiz.questions.exists():
        messages.error(request, 'Add at least one question before publishing.')
    elif quiz.is_published:
        messages.info(request, 'This quiz is already published.')
    else:
        quiz.is_published = True
        quiz.save(update_fields=['is_published'])
        messages.success(request, 'Quiz published for students in its assigned classes.')
    return redirect('assignments:quiz_detail', pk=quiz.pk)
