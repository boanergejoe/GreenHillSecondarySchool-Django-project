from django.contrib import admin

from .models import Assignment, Quiz, QuizAttempt, QuizQuestion, Submission


class SubmissionInline(admin.TabularInline):
    model = Submission
    extra = 0


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'due_date', 'created_by', 'is_published')
    list_filter = ('is_published', 'subject__school_classes')
    search_fields = ('title', 'subject__name')
    autocomplete_fields = ('subject', 'created_by')
    list_select_related = ('subject', 'created_by')
    date_hierarchy = 'due_date'
    inlines = [SubmissionInline]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'status', 'score', 'submitted_at')
    list_filter = ('status',)
    search_fields = ('assignment__title', 'student__user__first_name', 'student__student_id')
    autocomplete_fields = ('assignment', 'student', 'reviewed_by')
    list_select_related = ('assignment', 'student__user', 'reviewed_by')
    list_per_page = 25


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'created_by', 'is_published', 'created_at')
    list_filter = ('is_published', 'subject__school_classes')
    search_fields = ('title', 'subject__name')
    autocomplete_fields = ('subject', 'created_by')
    list_select_related = ('subject', 'created_by')


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'position', 'prompt', 'correct_option')
    search_fields = ('quiz__title', 'prompt')
    autocomplete_fields = ('quiz',)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'student', 'score', 'submitted_at')
    list_filter = ('quiz',)
    search_fields = ('quiz__title', 'student__student_id', 'student__user__first_name')
    autocomplete_fields = ('quiz', 'student')
