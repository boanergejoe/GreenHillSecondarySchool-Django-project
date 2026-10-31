from django.contrib import admin

from .models import Announcement, Notification


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'audience', 'is_published', 'is_public', 'event_date',
        'created_by', 'created_at',
    )
    list_filter = ('audience', 'is_published', 'is_public')
    search_fields = ('title', 'message')
    autocomplete_fields = ('created_by',)
    list_select_related = ('created_by',)
    date_hierarchy = 'created_at'
    list_per_page = 25


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('title', 'user__username')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    date_hierarchy = 'created_at'
    list_per_page = 25
