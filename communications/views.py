from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView

from accounts.models import User
from accounts.mixins import user_has_role
from school.generic import BaseCreateView, BaseDeleteView, BaseUpdateView

from .forms import AnnouncementForm
from .models import Announcement, Notification


def _audience_filter(user):
    if user_has_role(user, ()):
        return Q()
    mapping = {
        'student': [Announcement.Audience.ALL, Announcement.Audience.STUDENTS],
        'teacher': [Announcement.Audience.ALL, Announcement.Audience.TEACHERS],
        'parent': [Announcement.Audience.ALL, Announcement.Audience.PARENTS],
        'accountant': [Announcement.Audience.ALL, Announcement.Audience.ACCOUNTANTS],
    }
    return Q(audience__in=mapping.get(user.role, [Announcement.Audience.ALL]))


class AnnouncementListView(ListView):
    model = Announcement
    template_name = 'communications/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Announcement.objects.select_related('created_by')
        if not user_has_role(self.request.user, ()):
            qs = qs.filter(is_published=True).filter(_audience_filter(self.request.user))
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(message__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Announcements',
            'q': self.request.GET.get('q', ''),
            'can_manage': user_has_role(self.request.user, ()),
        })
        return context


class AnnouncementCreateView(BaseCreateView):
    model = Announcement
    form_class = AnnouncementForm
    page_title = 'Publish Announcement'
    success_url = reverse_lazy('communications:announcement_list')
    cancel_url_name = 'communications:announcement_list'
    success_message = 'Announcement published successfully.'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        announcement = self.object
        if announcement.is_published:
            role_map = {
                Announcement.Audience.STUDENTS: [User.Role.STUDENT],
                Announcement.Audience.TEACHERS: [User.Role.TEACHER],
                Announcement.Audience.PARENTS: [User.Role.PARENT],
                Announcement.Audience.ACCOUNTANTS: [User.Role.ACCOUNTANT],
            }
            users = User.objects.filter(is_active=True)
            if announcement.audience != Announcement.Audience.ALL:
                users = users.filter(role__in=role_map.get(announcement.audience, []))
            notifications = [
                Notification(
                    user=user,
                    title=announcement.title,
                    message=announcement.message[:240],
                    link=f'/communications/announcements/{announcement.pk}/',
                )
                for user in users
            ]
            Notification.objects.bulk_create(notifications)
        return response


class AnnouncementUpdateView(BaseUpdateView):
    model = Announcement
    form_class = AnnouncementForm
    page_title = 'Edit Announcement'
    success_url = reverse_lazy('communications:announcement_list')
    cancel_url_name = 'communications:announcement_list'
    success_message = 'Announcement updated successfully.'


class AnnouncementDeleteView(BaseDeleteView):
    model = Announcement
    page_title = 'Delete Announcement'
    success_url = reverse_lazy('communications:announcement_list')
    cancel_url_name = 'communications:announcement_list'


@login_required
def announcement_detail(request, pk):
    announcement = get_object_or_404(
        Announcement.objects.select_related('created_by'), pk=pk
    )
    if not user_has_role(request.user, ()):
        if not announcement.is_published:
            return redirect('communications:announcement_list')
        if not _audience_filter(request.user) or not Announcement.objects.filter(
            _audience_filter(request.user), pk=pk
        ).exists():
            messages.error(request, 'This announcement is not available to you.')
            return redirect('communications:announcement_list')
    return render(request, 'communications/announcement_detail.html', {
        'page_title': announcement.title,
        'announcement': announcement,
        'can_manage': user_has_role(request.user, ()),
    })


from django.shortcuts import render  # noqa: E402


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()
    return render(request, 'communications/notification_list.html', {
        'page_title': 'Notifications',
        'notifications': notifications,
    })


@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    if notification.link:
        return redirect(notification.link)
    return redirect('communications:notification_list')


@login_required
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('communications:notification_list')
