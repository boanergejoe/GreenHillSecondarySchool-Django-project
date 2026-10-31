from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from accounts.mixins import user_has_role
from academics.models import SchoolClass
from school.generic import BaseCreateView, BaseDeleteView, BaseListView, BaseUpdateView
from students.models import Student

from .forms import FeeForm, PaymentForm
from .models import Fee, Payment
from .services import active_fees_for_student

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:  # pragma: no cover
    colors = None


class FeeListView(BaseListView):
    model = Fee
    page_title = 'Fee Structure'
    allowed_roles = ('accountant',)
    search_fields = ['name', 'school_class__name', 'academic_year__name']
    columns = [
        ('Fee', 'name'), ('Applies To', 'class_scope'),
        ('Academic Year', 'academic_year.name'), ('Amount', 'amount'),
        ('Due Date', 'due_date'), ('Active', 'is_active'),
    ]
    create_url_name = 'finance:fee_create'
    edit_url_name = 'finance:fee_update'
    delete_url_name = 'finance:fee_delete'
    create_label = 'Add Fee'
    create_roles = ('accountant',)


class FeeCreateView(BaseCreateView):
    model = Fee
    form_class = FeeForm
    page_title = 'Add Fee'
    success_url = reverse_lazy('finance:fee_list')
    cancel_url_name = 'finance:fee_list'
    success_message = 'Fee structure created successfully.'
    allowed_roles = ('accountant',)
    required_field_exclusions = ('school_class',)


class FeeUpdateView(BaseUpdateView):
    model = Fee
    form_class = FeeForm
    page_title = 'Edit Fee'
    success_url = reverse_lazy('finance:fee_list')
    cancel_url_name = 'finance:fee_list'
    success_message = 'Fee structure updated successfully.'
    allowed_roles = ('accountant',)


class FeeDeleteView(BaseDeleteView):
    model = Fee
    page_title = 'Delete Fee'
    success_url = reverse_lazy('finance:fee_list')
    cancel_url_name = 'finance:fee_list'
    allowed_roles = ('accountant',)


class PaymentListView(BaseListView):
    model = Payment
    page_title = 'Payments'
    allowed_roles = ('accountant',)
    search_fields = [
        'receipt_number', 'student__student_id', 'student__user__first_name',
        'student__user__last_name', 'reference',
    ]
    columns = [
        ('Receipt', 'receipt_number'), ('Student', 'student.user.display_name'),
        ('Student ID', 'student.student_id'), ('Fee', 'fee.name'),
        ('Amount', 'amount'), ('Method', 'get_method_display'), ('Date', 'payment_date'),
    ]
    create_url_name = 'finance:payment_create'
    edit_url_name = 'finance:payment_update'
    delete_url_name = 'finance:payment_delete'
    detail_url_name = 'finance:payment_detail'
    create_label = 'Record Payment'
    create_roles = ('accountant',)

    def get_queryset(self):
        qs = Payment.objects.select_related('student__user', 'fee')
        q = self.request.GET.get('q', '').strip()
        method = self.request.GET.get('method', '').strip()
        start = self.request.GET.get('start_date', '').strip()
        end = self.request.GET.get('end_date', '').strip()
        if q:
            qs = qs.filter(
                Q(receipt_number__icontains=q)
                | Q(student__student_id__icontains=q)
                | Q(student__user__first_name__icontains=q)
                | Q(student__user__last_name__icontains=q)
            )
        if method:
            qs = qs.filter(method=method)
        if start:
            qs = qs.filter(payment_date__gte=start)
        if end:
            qs = qs.filter(payment_date__lte=end)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'methods': Payment.Method.choices,
            'selected_method': self.request.GET.get('method', ''),
            'start_date': self.request.GET.get('start_date', ''),
            'end_date': self.request.GET.get('end_date', ''),
            'total_filtered': self.get_queryset().aggregate(total=Sum('amount'))['total'] or 0,
        })
        return context


class PaymentCreateView(BaseCreateView):
    model = Payment
    form_class = PaymentForm
    page_title = 'Record Payment'
    success_url = reverse_lazy('finance:payment_list')
    cancel_url_name = 'finance:payment_list'
    success_message = 'Payment recorded successfully.'
    allowed_roles = ('accountant',)

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)


class PaymentUpdateView(BaseUpdateView):
    model = Payment
    form_class = PaymentForm
    page_title = 'Edit Payment'
    success_url = reverse_lazy('finance:payment_list')
    cancel_url_name = 'finance:payment_list'
    success_message = 'Payment updated successfully.'
    allowed_roles = ('accountant',)


class PaymentDeleteView(BaseDeleteView):
    model = Payment
    page_title = 'Delete Payment'
    success_url = reverse_lazy('finance:payment_list')
    cancel_url_name = 'finance:payment_list'
    allowed_roles = ('accountant',)


def _payment_access(user, payment):
    if user_has_role(user, ('accountant',)):
        return True
    if user.role == 'student' and payment.student.user_id == user.id:
        return True
    if user.role == 'parent' and payment.student.parent_id and payment.student.parent.user_id == user.id:
        return True
    return False


@login_required
def payment_detail(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related('student__user', 'student__school_class', 'fee'),
        pk=pk,
    )
    if not _payment_access(request.user, payment):
        raise PermissionDenied('You cannot view this payment.')
    return render(request, 'finance/payment_detail.html', {
        'page_title': f'Payment - {payment.receipt_number}',
        'payment': payment,
    })


@login_required
def receipt_pdf(request, pk):
    if colors is None:
        messages.error(request, 'PDF generation requires the reportlab package.')
        return redirect('finance:payment_detail', pk=pk)

    payment = get_object_or_404(
        Payment.objects.select_related('student__user', 'student__school_class', 'fee'),
        pk=pk,
    )
    if not _payment_access(request.user, payment):
        raise PermissionDenied('You cannot download this receipt.')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt-{payment.receipt_number}.pdf"'
    doc = SimpleDocTemplate(
        response, pagesize=A5, topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(settings.SCHOOL_NAME, styles['Title']),
        Paragraph(settings.SCHOOL_ADDRESS, styles['Normal']),
        Paragraph(settings.SCHOOL_PHONE, styles['Normal']),
        Spacer(1, 10),
        Paragraph('OFFICIAL PAYMENT RECEIPT', styles['Heading2']),
        Spacer(1, 8),
    ]
    data = [
        ['Receipt No.', payment.receipt_number],
        ['Student', payment.student.full_name],
        ['Student ID', payment.student.student_id],
        ['Class', payment.student.school_class.name if payment.student.school_class else '-'],
        ['Fee', payment.fee.name if payment.fee else 'General payment'],
        ['Amount', f'{payment.amount:,.2f}'],
        ['Method', payment.get_method_display()],
        ['Date', payment.payment_date.strftime('%d %b %Y')],
        ['Reference', payment.reference or '-'],
        ['Received by', payment.recorded_by.display_name if payment.recorded_by else '-'],
    ]
    table = Table(data, colWidths=[35 * mm, 100 * mm])
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dce6df')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e6f2ea')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f'Generated on {timezone.now().strftime("%d %b %Y %H:%M")}', styles['Italic']
    ))
    doc.build(story)
    return response


def _statement_access(user, student):
    if user_has_role(user, ('accountant',)):
        return True
    if user.role == 'student' and student.user_id == user.id:
        return True
    if user.role == 'parent' and student.parent_id and student.parent.user_id == user.id:
        return True
    return False


@login_required
def fee_statement(request, student_id):
    student = get_object_or_404(
        Student.objects.select_related('user', 'school_class'), pk=student_id
    )
    if not _statement_access(request.user, student):
        raise PermissionDenied('You cannot view this fee statement.')

    fees = active_fees_for_student(student)
    payments = student.payments.select_related('fee').order_by('-payment_date')
    expected = fees.aggregate(total=Sum('amount'))['total'] or 0
    paid = payments.aggregate(total=Sum('amount'))['total'] or 0
    balance = max(expected - paid, 0)

    return render(request, 'finance/fee_statement.html', {
        'page_title': f'Fee Statement - {student.full_name}',
        'student': student,
        'fees': fees,
        'payments': payments,
        'expected': expected,
        'paid': paid,
        'balance': balance,
    })


@login_required
def financial_overview(request):
    if not user_has_role(request.user, ('accountant',)):
        raise PermissionDenied('You cannot access financial reports.')

    start = request.GET.get('start_date', '')
    end = request.GET.get('end_date', '')
    payments = Payment.objects.all()
    if start:
        payments = payments.filter(payment_date__gte=start)
    if end:
        payments = payments.filter(payment_date__lte=end)

    total = payments.aggregate(total=Sum('amount'))['total'] or 0
    by_method = (
        payments.values('method').annotate(total=Sum('amount')).order_by('-total')
    )
    by_class = (
        payments.values('student__school_class__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    recent = payments.select_related('student__user', 'fee')[:10]

    return render(request, 'finance/financial_overview.html', {
        'page_title': 'Financial Overview',
        'total': total,
        'by_method': by_method,
        'by_class': by_class,
        'recent': recent,
        'start_date': start,
        'end_date': end,
        'payment_count': payments.count(),
    })
