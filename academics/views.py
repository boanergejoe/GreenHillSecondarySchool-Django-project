from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View

from accounts.mixins import RoleRequiredMixin
from accounts.models import User
from .access import teacher_subjects
from school.generic import BaseCreateView, BaseDeleteView, BaseListView, BaseUpdateView

from .forms import (
    AcademicNoticeForm, AcademicYearForm, DepartmentForm, EnrollmentForm, LessonPlanForm,
    ExaminationSessionForm, SchoolClassForm, SubjectForm, TeacherAttendanceForm,
    SyllabusCoverageForm, TeachingObservationForm, TeachingScheduleForm,
    TermForm,
)
from .models import (
    AcademicAuditLog, AcademicYear, Department, Enrollment,
    ExaminationSession, LessonPlan, SchoolClass, Subject, SyllabusCoverage,
    TeacherAttendance, TeachingObservation, TeachingSchedule, Term,
)


class AcademicAuditCreateMixin:
    def form_valid(self, form):
        response = super().form_valid(form)
        AcademicAuditLog.objects.create(
            actor=self.request.user,
            action='academic_record_created',
            object_type=self.model.__name__,
            object_id=self.object.pk,
            summary=f'{self.page_title}: {self.object}.',
        )
        return response


class AcademicAuditUpdateMixin:
    def form_valid(self, form):
        response = super().form_valid(form)
        AcademicAuditLog.objects.create(
            actor=self.request.user,
            action='academic_record_updated',
            object_type=self.model.__name__,
            object_id=self.object.pk,
            summary=f'{self.page_title}: {self.object}.',
        )
        return response


class AcademicAuditDeleteMixin:
    def form_valid(self, form):
        AcademicAuditLog.objects.create(
            actor=self.request.user,
            action='academic_record_deleted',
            object_type=self.model.__name__,
            object_id=self.object.pk,
            summary=f'{self.page_title}: {self.object}.',
        )
        return super().form_valid(form)


def _notify_dos_syllabus_update(coverage):
    from communications.models import Notification

    Notification.objects.bulk_create([
        Notification(
            user=dos_user,
            title='Syllabus coverage update',
            message=(
                f'{coverage.subject} / {coverage.school_class}: '
                f'{coverage.topics_completed} of '
                f'{coverage.topics_planned} topics are complete.'
            ),
            link=reverse('academics:syllabus_coverage_list'),
        )
        for dos_user in User.objects.filter(
            role=User.Role.DOS, is_active=True
        )
    ])


class DepartmentListView(BaseListView):
    model = Department
    page_title = 'Departments'
    allowed_roles = ('dos',)
    search_fields = ['name', 'code']
    columns = [('Name', 'name'), ('Code', 'code'), ('Description', 'description')]
    create_url_name = 'academics:department_create'
    edit_url_name = 'academics:department_update'
    delete_url_name = 'academics:department_delete'
    create_label = 'Add Department'


class SyllabusCoverageListView(BaseListView):
    model = SyllabusCoverage
    page_title = 'Syllabus Coverage'
    allowed_roles = ('dos', 'teacher')
    search_fields = [
        'school_class__name', 'subject__name', 'term', 'academic_year__name',
    ]
    columns = [
        ('Academic Year', 'academic_year.name'), ('Term', 'term'),
        ('Class', 'school_class.name'), ('Subject', 'subject.name'),
        ('Topics Completed', 'topics_completed'), ('Topics Planned', 'topics_planned'),
        ('Progress', 'completion_percentage'),
    ]
    create_url_name = 'academics:syllabus_coverage_create'
    edit_url_name = 'academics:syllabus_coverage_update'
    delete_url_name = 'academics:syllabus_coverage_delete'
    create_label = 'Update Coverage'

    def get_queryset(self):
        coverage = SyllabusCoverage.objects.select_related(
            'academic_year', 'school_class', 'subject', 'updated_by'
        )
        if self.request.user.role == User.Role.TEACHER:
            coverage = coverage.filter(subject__in=teacher_subjects(self.request.user))
        return coverage

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_create'] = self.request.user.role in (
            User.Role.DOS, User.Role.TEACHER
        )
        return context


class SyllabusCoverageCreateView(BaseCreateView):
    model = SyllabusCoverage
    form_class = SyllabusCoverageForm
    page_title = 'Update Syllabus Coverage'
    success_url = reverse_lazy('academics:syllabus_coverage_list')
    cancel_url_name = 'academics:syllabus_coverage_list'
    allowed_roles = ('dos', 'teacher')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        if (
            self.request.user.role == User.Role.TEACHER
            and self.object.completion_percentage < 100
        ):
            _notify_dos_syllabus_update(self.object)
        AcademicAuditLog.objects.create(
            actor=self.request.user,
            action='syllabus_coverage_updated',
            object_type='SyllabusCoverage',
            object_id=self.object.pk,
            summary=(
                f'{self.object.subject} / {self.object.school_class}: '
                f'{self.object.topics_completed} of {self.object.topics_planned} '
                f'topics completed for {self.object.term}.'
            ),
        )
        return response


class SyllabusCoverageUpdateView(BaseUpdateView):
    model = SyllabusCoverage
    form_class = SyllabusCoverageForm
    page_title = 'Edit Syllabus Coverage'
    success_url = reverse_lazy('academics:syllabus_coverage_list')
    cancel_url_name = reverse_lazy('academics:syllabus_coverage_list')
    allowed_roles = ('dos', 'teacher')

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == User.Role.TEACHER:
            queryset = queryset.filter(
                subject__in=teacher_subjects(self.request.user)
            )
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        if (
            self.request.user.role == User.Role.TEACHER
            and self.object.completion_percentage < 100
        ):
            _notify_dos_syllabus_update(self.object)
        AcademicAuditLog.objects.create(
            actor=self.request.user,
            action='syllabus_coverage_updated',
            object_type='SyllabusCoverage',
            object_id=self.object.pk,
            summary=(
                f'{self.object.subject} / {self.object.school_class}: '
                f'{self.object.topics_completed} of {self.object.topics_planned} '
                f'topics completed for {self.object.term}.'
            ),
        )
        return response


class SyllabusCoverageDeleteView(BaseDeleteView):
    model = SyllabusCoverage
    page_title = 'Delete Syllabus Coverage'
    success_url = reverse_lazy('academics:syllabus_coverage_list')
    cancel_url_name = reverse_lazy('academics:syllabus_coverage_list')
    allowed_roles = ('dos',)


class LessonPlanListView(BaseListView):
    model = LessonPlan
    page_title = 'Lesson Plans'
    allowed_roles = ('teacher', 'dos')
    search_fields = [
        'topic', 'teacher__first_name', 'teacher__last_name',
        'subject__name', 'school_class__name',
    ]
    columns = [
        ('Date', 'lesson_date'), ('Topic', 'topic'), ('Teacher', 'teacher.display_name'),
        ('Class', 'school_class.name'), ('Subject', 'subject.name'),
        ('Status', 'get_status_display'),
    ]
    create_url_name = 'academics:lesson_plan_create'
    edit_url_name = 'academics:lesson_plan_update'
    detail_url_name = None
    create_label = 'Submit Lesson Plan'

    def get_queryset(self):
        plans = LessonPlan.objects.select_related(
            'academic_year', 'school_class', 'subject', 'teacher', 'reviewed_by'
        )
        if self.request.user.role == User.Role.TEACHER:
            plans = plans.filter(teacher=self.request.user)
        status = self.request.GET.get('status', '').strip()
        if status in LessonPlan.Status.values:
            plans = plans.filter(status=status)
        return plans

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_choices': LessonPlan.Status.choices,
            'selected_status': self.request.GET.get('status', ''),
            'can_review': self.request.user.role == User.Role.DOS,
            'can_create': self.request.user.role in (User.Role.DOS, User.Role.TEACHER),
        })
        return context


class LessonPlanCreateView(BaseCreateView):
    model = LessonPlan
    form_class = LessonPlanForm
    page_title = 'Submit Lesson Plan'
    success_url = reverse_lazy('academics:lesson_plan_list')
    cancel_url_name = 'academics:lesson_plan_list'
    allowed_roles = ('teacher', 'dos')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        if self.request.user.role == User.Role.TEACHER:
            form.instance.teacher = self.request.user
        else:
            teacher = form.cleaned_data['subject'].teacher
            if not teacher:
                form.add_error(
                    'subject',
                    'Assign a teacher to this subject before submitting its lesson plan.',
                )
                return self.form_invalid(form)
            form.instance.teacher = teacher
        response = super().form_valid(form)
        AcademicAuditLog.objects.create(
            actor=self.request.user,
            action='lesson_plan_submitted',
            object_type='LessonPlan',
            object_id=self.object.pk,
            summary=f'{self.object.teacher} submitted "{self.object.topic}".',
        )
        return response


class LessonPlanUpdateView(BaseUpdateView):
    model = LessonPlan
    form_class = LessonPlanForm
    page_title = 'Edit Lesson Plan'
    success_url = reverse_lazy('academics:lesson_plan_list')
    cancel_url_name = reverse_lazy('academics:lesson_plan_list')
    allowed_roles = ('teacher', 'dos')

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == User.Role.TEACHER:
            queryset = queryset.filter(
                teacher=self.request.user,
                status=LessonPlan.Status.PENDING,
            )
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        AcademicAuditLog.objects.create(
            actor=self.request.user,
            action='lesson_plan_updated',
            object_type='LessonPlan',
            object_id=self.object.pk,
            summary=f'{self.object.teacher} updated "{self.object.topic}".',
        )
        return response


class LessonPlanReviewView(RoleRequiredMixin, View):
    allowed_roles = ('dos',)

    def post(self, request, pk):
        lesson_plan = get_object_or_404(
            LessonPlan.objects.select_related('teacher', 'subject', 'school_class'),
            pk=pk,
        )
        status = request.POST.get('status')
        if status not in (LessonPlan.Status.APPROVED, LessonPlan.Status.REVISION):
            messages.error(request, 'Choose a valid lesson-plan review status.')
            return redirect('academics:lesson_plan_list')
        review_note = request.POST.get('review_note', '').strip()
        if status == LessonPlan.Status.REVISION and not review_note:
            messages.error(request, 'Add a review note when requesting revisions.')
            return redirect('academics:lesson_plan_list')

        lesson_plan.status = status
        lesson_plan.review_note = review_note
        lesson_plan.reviewed_by = request.user
        lesson_plan.reviewed_at = timezone.now()
        lesson_plan.save(update_fields=[
            'status', 'review_note', 'reviewed_by', 'reviewed_at', 'updated_at',
        ])
        from communications.models import Notification

        Notification.objects.create(
            user=lesson_plan.teacher,
            title=f'Lesson plan {lesson_plan.get_status_display().lower()}',
            message=(
                f'{lesson_plan.topic} ({lesson_plan.school_class}, '
                f'{lesson_plan.subject}): {review_note or "No additional note."}'
            ),
            link=reverse('academics:lesson_plan_list'),
        )
        AcademicAuditLog.objects.create(
            actor=request.user,
            action='lesson_plan_reviewed',
            object_type='LessonPlan',
            object_id=lesson_plan.pk,
            summary=(
                f'{lesson_plan.get_status_display()}: "{lesson_plan.topic}" '
                f'for {lesson_plan.teacher}.'
            ),
        )
        messages.success(
            request, f'Lesson plan {lesson_plan.get_status_display().lower()}.'
        )
        return redirect('academics:lesson_plan_list')


class TeachingObservationListView(BaseListView):
    model = TeachingObservation
    page_title = 'Teaching Observations'
    allowed_roles = ('dos',)
    search_fields = [
        'teacher__first_name', 'teacher__last_name', 'subject__name',
        'school_class__name', 'strengths',
    ]
    columns = [
        ('Date', 'observed_on'), ('Teacher', 'teacher.display_name'),
        ('Class', 'school_class.name'), ('Subject', 'subject.name'),
        ('Lesson Prepared', 'lesson_prepared'), ('Rating', 'rating'),
    ]
    create_url_name = 'academics:observation_create'
    create_label = 'Record Observation'

    def get_queryset(self):
        return TeachingObservation.objects.select_related(
            'teacher', 'school_class', 'subject', 'observer'
        )


class TeachingObservationCreateView(BaseCreateView):
    model = TeachingObservation
    form_class = TeachingObservationForm
    page_title = 'Record Teaching Observation'
    success_url = reverse_lazy('academics:observation_list')
    cancel_url_name = reverse_lazy('academics:observation_list')
    allowed_roles = ('dos',)

    def form_valid(self, form):
        form.instance.observer = self.request.user
        response = super().form_valid(form)
        AcademicAuditLog.objects.create(
            actor=self.request.user,
            action='teaching_observation_recorded',
            object_type='TeachingObservation',
            object_id=self.object.pk,
            summary=(
                f'Observed {self.object.teacher} on {self.object.observed_on}; '
                f'rating {self.object.rating}/5.'
            ),
        )
        return response


class TeacherAttendanceListView(BaseListView):
    model = TeacherAttendance
    page_title = 'Teacher Attendance'
    allowed_roles = ('dos',)
    search_fields = ['teacher__first_name', 'teacher__last_name', 'teacher__username']
    columns = [
        ('Date', 'date'), ('Teacher', 'teacher.display_name'),
        ('Status', 'get_status_display'), ('Check in', 'check_in'),
        ('Check out', 'check_out'), ('Note', 'note'),
    ]
    create_url_name = 'academics:teacher_attendance_create'
    edit_url_name = 'academics:teacher_attendance_update'
    delete_url_name = 'academics:teacher_attendance_delete'
    create_label = 'Record Teacher Attendance'

    def get_queryset(self):
        return TeacherAttendance.objects.select_related('teacher', 'recorded_by')


class TeacherAttendanceCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = TeacherAttendance
    form_class = TeacherAttendanceForm
    page_title = 'Record Teacher Attendance'
    success_url = reverse_lazy('academics:teacher_attendance_list')
    cancel_url_name = reverse_lazy('academics:teacher_attendance_list')
    allowed_roles = ('dos',)

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)


class TeacherAttendanceUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = TeacherAttendance
    form_class = TeacherAttendanceForm
    page_title = 'Edit Teacher Attendance'
    success_url = reverse_lazy('academics:teacher_attendance_list')
    cancel_url_name = reverse_lazy('academics:teacher_attendance_list')
    allowed_roles = ('dos',)


class TeacherAttendanceDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = TeacherAttendance
    page_title = 'Delete Teacher Attendance'
    success_url = reverse_lazy('academics:teacher_attendance_list')
    cancel_url_name = reverse_lazy('academics:teacher_attendance_list')
    allowed_roles = ('dos',)


class AcademicAuditLogListView(BaseListView):
    model = AcademicAuditLog
    page_title = 'Academic Activity'
    allowed_roles = ('dos',)
    search_fields = ['action', 'object_type', 'summary', 'actor__username']
    columns = [
        ('Date', 'created_at'), ('Action', 'action'), ('User', 'actor.username'),
        ('Record Type', 'object_type'), ('Summary', 'summary'),
    ]

    def get_queryset(self):
        return AcademicAuditLog.objects.select_related('actor')


class AcademicNoticeCreateView(RoleRequiredMixin, View):
    allowed_roles = ('dos',)
    template_name = 'academics/academic_notice_form.html'

    def get(self, request):
        return render(request, self.template_name, {
            'page_title': 'Send Academic Notice',
            'form': AcademicNoticeForm(),
        })

    def post(self, request):
        form = AcademicNoticeForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'page_title': 'Send Academic Notice',
                'form': form,
            })

        from communications.models import Announcement, Notification

        recipient = form.cleaned_data['recipient']
        announcement = None
        if recipient != 'department':
            audience = (
                Announcement.Audience.STUDENTS
                if recipient == 'students'
                else Announcement.Audience.TEACHERS
            )
            announcement = Announcement.objects.create(
                title=form.cleaned_data['title'],
                message=form.cleaned_data['message'],
                audience=audience,
                is_published=True,
                is_public=False,
                created_by=request.user,
            )
        recipients = User.objects.filter(is_active=True)
        if recipient == 'teachers':
            recipients = recipients.filter(role=User.Role.TEACHER)
        elif recipient == 'students':
            recipients = recipients.filter(role=User.Role.STUDENT)
        else:
            recipients = recipients.filter(
                role=User.Role.TEACHER,
                teacher_profile__department=form.cleaned_data['department'],
            )
        recipient_ids = list(recipients.values_list('pk', flat=True))
        notification_link = (
            reverse('communications:announcement_detail', args=[announcement.pk])
            if announcement else reverse('communications:notification_list')
        )
        Notification.objects.bulk_create([
            Notification(
                user_id=user_id,
                title=form.cleaned_data['title'],
                message=form.cleaned_data['message'][:240],
                link=notification_link,
            )
            for user_id in recipient_ids
        ])
        AcademicAuditLog.objects.create(
            actor=request.user,
            action='academic_notice_sent',
            object_type='AcademicNotice',
            object_id=announcement.pk if announcement else '',
            summary=(
                f'Sent "{form.cleaned_data["title"]}" to {len(recipient_ids)} '
                f'academic recipient(s).'
            ),
        )
        messages.success(
            request, f'Academic notice sent to {len(recipient_ids)} recipient(s).'
        )
        return redirect('academics:academic_activity')


class TeachingScheduleListView(BaseListView):
    model = TeachingSchedule
    page_title = 'Teaching Schedule'
    allowed_roles = ('dos', 'teacher')
    search_fields = [
        'school_class__name', 'subject__name', 'teacher__first_name',
        'teacher__last_name', 'room',
    ]
    columns = [
        ('Day', 'get_weekday_display'), ('Time', 'time_range'),
        ('Class', 'school_class.name'), ('Subject', 'subject.name'),
        ('Teacher', 'teacher.display_name'), ('Room', 'room'),
        ('Academic Year', 'academic_year.name'),
    ]
    create_url_name = 'academics:teaching_schedule_create'
    edit_url_name = 'academics:teaching_schedule_update'
    delete_url_name = 'academics:teaching_schedule_delete'
    create_label = 'Add Schedule Period'

    def get_queryset(self):
        schedules = TeachingSchedule.objects.select_related(
            'academic_year', 'school_class', 'subject', 'teacher'
        )
        if self.request.user.role == User.Role.TEACHER:
            schedules = schedules.filter(teacher=self.request.user)
        return schedules

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_create'] = self.request.user.role == User.Role.DOS
        return context


class TeachingScheduleCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = TeachingSchedule
    form_class = TeachingScheduleForm
    page_title = 'Add Teaching Schedule Period'
    success_url = reverse_lazy('academics:teaching_schedule_list')
    cancel_url_name = reverse_lazy('academics:teaching_schedule_list')
    allowed_roles = ('dos',)


class TeachingScheduleUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = TeachingSchedule
    form_class = TeachingScheduleForm
    page_title = 'Edit Teaching Schedule Period'
    success_url = reverse_lazy('academics:teaching_schedule_list')
    cancel_url_name = reverse_lazy('academics:teaching_schedule_list')
    allowed_roles = ('dos',)


class TeachingScheduleDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = TeachingSchedule
    page_title = 'Delete Teaching Schedule Period'
    success_url = reverse_lazy('academics:teaching_schedule_list')
    cancel_url_name = reverse_lazy('academics:teaching_schedule_list')
    allowed_roles = ('dos',)


class ExaminationSessionListView(BaseListView):
    model = ExaminationSession
    page_title = 'Examination Timetable'
    allowed_roles = ('dos', 'teacher')
    search_fields = [
        'examination__name', 'school_class__name', 'subject__name',
        'venue', 'invigilators__first_name', 'invigilators__last_name',
    ]
    columns = [
        ('Date', 'exam_date'), ('Examination', 'examination.name'),
        ('Class', 'school_class.name'), ('Subject', 'subject.name'),
        ('Time', 'time_range'), ('Venue', 'venue'),
        ('Invigilators', 'invigilator_names'),
    ]
    create_url_name = 'academics:examination_session_create'
    edit_url_name = 'academics:examination_session_update'
    delete_url_name = 'academics:examination_session_delete'
    create_label = 'Add Timetable Session'

    def get_queryset(self):
        sessions = ExaminationSession.objects.select_related(
            'examination', 'school_class', 'subject'
        ).prefetch_related('invigilators')
        if self.request.user.role == User.Role.TEACHER:
            sessions = sessions.filter(invigilators=self.request.user)
        return sessions.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_create'] = self.request.user.role == User.Role.DOS
        return context


class ExaminationSessionCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = ExaminationSession
    form_class = ExaminationSessionForm
    page_title = 'Add Examination Timetable Session'
    success_url = reverse_lazy('academics:examination_session_list')
    cancel_url_name = reverse_lazy('academics:examination_session_list')
    allowed_roles = ('dos',)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        from communications.models import Notification

        Notification.objects.bulk_create([
            Notification(
                user=teacher,
                title=f'Examination duty: {self.object.examination.name}',
                message=(
                    f'You are assigned to invigilate {self.object.subject} for '
                    f'{self.object.school_class} on {self.object.exam_date} '
                    f'from {self.object.start_time} to {self.object.end_time} '
                    f'at {self.object.venue}.'
                ),
                link=reverse('academics:examination_session_list'),
            )
            for teacher in self.object.invigilators.all()
        ])
        return response


class ExaminationSessionUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = ExaminationSession
    form_class = ExaminationSessionForm
    page_title = 'Edit Examination Timetable Session'
    success_url = reverse_lazy('academics:examination_session_list')
    cancel_url_name = reverse_lazy('academics:examination_session_list')
    allowed_roles = ('dos',)


class ExaminationSessionDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = ExaminationSession
    page_title = 'Delete Examination Timetable Session'
    success_url = reverse_lazy('academics:examination_session_list')
    cancel_url_name = reverse_lazy('academics:examination_session_list')
    allowed_roles = ('dos',)
class DepartmentCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = Department
    form_class = DepartmentForm
    page_title = 'Add Department'
    success_url = reverse_lazy('academics:department_list')
    cancel_url_name = 'academics:department_list'
    allowed_roles = ('dos',)


class DepartmentUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = Department
    form_class = DepartmentForm
    page_title = 'Edit Department'
    success_url = reverse_lazy('academics:department_list')
    cancel_url_name = 'academics:department_list'
    allowed_roles = ('dos',)


class DepartmentDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = Department
    page_title = 'Delete Department'
    success_url = reverse_lazy('academics:department_list')
    cancel_url_name = 'academics:department_list'
    allowed_roles = ('dos',)


class AcademicYearListView(BaseListView):
    model = AcademicYear
    page_title = 'Academic Years'
    allowed_roles = ('dos',)
    search_fields = ['name']
    columns = [
        ('Name', 'name'), ('Start Date', 'start_date'), ('End Date', 'end_date'),
        ('Current', 'is_current'),
    ]
    create_url_name = 'academics:year_create'
    edit_url_name = 'academics:year_update'
    delete_url_name = 'academics:year_delete'
    create_label = 'Add Academic Year'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['term_list_url'] = reverse_lazy('academics:term_list')
        return context


class AcademicYearCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = AcademicYear
    form_class = AcademicYearForm
    page_title = 'Add Academic Year'
    success_url = reverse_lazy('academics:year_list')
    cancel_url_name = 'academics:year_list'
    allowed_roles = ('dos',)
    required_field_exclusions = tuple(
        field
        for term_index in range(1, 4)
        for field in (
            f'term_{term_index}_start_date',
            f'term_{term_index}_end_date',
        )
    )


class AcademicYearUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = AcademicYear
    form_class = AcademicYearForm
    page_title = 'Edit Academic Year'
    success_url = reverse_lazy('academics:year_list')
    cancel_url_name = 'academics:year_list'
    allowed_roles = ('dos',)


class AcademicYearDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = AcademicYear
    page_title = 'Delete Academic Year'
    success_url = reverse_lazy('academics:year_list')
    cancel_url_name = 'academics:year_list'
    allowed_roles = ('dos',)


class TermListView(BaseListView):
    model = Term
    page_title = 'Terms'
    allowed_roles = ('dos',)
    search_fields = ['name', 'academic_year__name']
    columns = [
        ('Term', 'name'), ('Academic Year', 'academic_year.name'),
        ('Start Date', 'start_date'), ('End Date', 'end_date'), ('Current', 'is_current'),
    ]
    create_url_name = 'academics:term_create'
    edit_url_name = 'academics:term_update'
    delete_url_name = 'academics:term_delete'
    create_label = 'Add Term'


class TermCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = Term
    form_class = TermForm
    page_title = 'Add Term'
    success_url = reverse_lazy('academics:term_list')
    cancel_url_name = 'academics:term_list'
    allowed_roles = ('dos',)


class TermUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = Term
    form_class = TermForm
    page_title = 'Edit Term'
    success_url = reverse_lazy('academics:term_list')
    cancel_url_name = 'academics:term_list'
    allowed_roles = ('dos',)


class TermDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = Term
    page_title = 'Delete Term'
    success_url = reverse_lazy('academics:term_list')
    cancel_url_name = 'academics:term_list'
    allowed_roles = ('dos',)


class SchoolClassListView(BaseListView):
    model = SchoolClass
    page_title = 'Classes'
    allowed_roles = ('teacher', 'accountant', 'dos')
    search_fields = ['name', 'level', 'stream', 'room']
    columns = [
        ('Class', 'name'), ('Level', 'level'), ('Stream', 'stream'),
        ('Department', 'department.name'), ('Academic Year', 'academic_year.name'),
        ('Class Teacher', 'class_teacher.display_name'), ('Students', 'student_count'),
        ('Capacity', 'capacity'),
    ]
    create_url_name = 'academics:class_create'
    edit_url_name = 'academics:class_update'
    delete_url_name = 'academics:class_delete'
    create_label = 'Add Class'


class SchoolClassCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = SchoolClass
    form_class = SchoolClassForm
    page_title = 'Add Class'
    success_url = reverse_lazy('academics:class_list')
    cancel_url_name = 'academics:class_list'
    allowed_roles = ('dos',)
    required_field_exclusions = ('stream', 'department', 'class_teacher')


class SchoolClassUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = SchoolClass
    form_class = SchoolClassForm
    page_title = 'Edit Class'
    success_url = reverse_lazy('academics:class_list')
    cancel_url_name = 'academics:class_list'
    allowed_roles = ('dos',)


class SchoolClassDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = SchoolClass
    page_title = 'Delete Class'
    success_url = reverse_lazy('academics:class_list')
    cancel_url_name = 'academics:class_list'
    allowed_roles = ('dos',)


class SubjectListView(BaseListView):
    model = Subject
    page_title = 'Subjects'
    allowed_roles = ('teacher', 'accountant', 'dos')
    search_fields = [
        'name', 'code', 'school_classes__name', 'teacher__first_name',
        'departments__name',
    ]
    columns = [
        ('Code', 'code'), ('Subject', 'name'),
        ('Department(s)', 'department_names'), ('Class(es)', 'school_class_names'),
        ('Teacher', 'teacher.display_name'), ('Academic Year', 'academic_year.name'),
        ('Term', 'term'), ('Active', 'is_active'),
    ]
    create_url_name = 'academics:subject_create'
    edit_url_name = 'academics:subject_update'
    delete_url_name = 'academics:subject_delete'
    create_label = 'Add Subject'

    def get_queryset(self):
        qs = Subject.objects.select_related(
            'teacher', 'academic_year'
        ).prefetch_related('departments')
        qs = qs.prefetch_related('school_classes')
        if self.request.user.role == 'teacher':
            qs = teacher_subjects(self.request.user).select_related(
                'teacher', 'academic_year'
            ).prefetch_related('departments', 'school_classes')
        return qs


class SubjectCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = Subject
    form_class = SubjectForm
    page_title = 'Add Subject'
    success_url = reverse_lazy('academics:subject_list')
    cancel_url_name = 'academics:subject_list'
    allowed_roles = ('dos',)


class SubjectUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = Subject
    form_class = SubjectForm
    page_title = 'Edit Subject'
    success_url = reverse_lazy('academics:subject_list')
    cancel_url_name = 'academics:subject_list'
    allowed_roles = ('dos',)


class SubjectDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = Subject
    page_title = 'Delete Subject'
    success_url = reverse_lazy('academics:subject_list')
    cancel_url_name = 'academics:subject_list'
    allowed_roles = ('dos',)


class EnrollmentListView(BaseListView):
    model = Enrollment
    page_title = 'Enrollments'
    allowed_roles = ('teacher', 'accountant', 'registrar', 'dos')
    search_fields = ['student__user__first_name', 'student__student_id']
    columns = [
        ('Student', 'student.user.display_name'), ('Student ID', 'student.student_id'),
        ('Class', 'school_class.name'), ('Academic Year', 'academic_year.name'),
        ('Term', 'term'), ('Enrolled On', 'enrolled_on'),
        ('Active', 'is_active'),
    ]
    create_url_name = 'academics:enrollment_create'
    edit_url_name = 'academics:enrollment_update'
    delete_url_name = 'academics:enrollment_delete'
    create_label = 'Add Enrollment'


class EnrollmentCreateView(AcademicAuditCreateMixin, BaseCreateView):
    model = Enrollment
    form_class = EnrollmentForm
    page_title = 'Add Enrollment'
    success_url = reverse_lazy('academics:enrollment_list')
    cancel_url_name = 'academics:enrollment_list'
    allowed_roles = ('registrar', 'accountant')


class EnrollmentUpdateView(AcademicAuditUpdateMixin, BaseUpdateView):
    model = Enrollment
    form_class = EnrollmentForm
    page_title = 'Edit Enrollment'
    success_url = reverse_lazy('academics:enrollment_list')
    cancel_url_name = 'academics:enrollment_list'
    allowed_roles = ('registrar', 'accountant')


class EnrollmentDeleteView(AcademicAuditDeleteMixin, BaseDeleteView):
    model = Enrollment
    page_title = 'Delete Enrollment'
    success_url = reverse_lazy('academics:enrollment_list')
    cancel_url_name = 'academics:enrollment_list'
    allowed_roles = ('registrar', 'accountant')
