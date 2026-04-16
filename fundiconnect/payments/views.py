from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from .models import Commission, Dispute, Escrow, Invoice, Milestone, Payment


@login_required
def payments(request):
    user = request.user
    escrows = Escrow.objects.filter(Q(client=user) | Q(artisan=user)).select_related('job')
    invoices = Invoice.objects.filter(Q(issuer=user) | Q(recipient=user)).select_related('job', 'issuer', 'recipient')
    payments_qs = Payment.objects.filter(Q(payer=user) | Q(payee=user)).select_related('invoice', 'invoice__job')
    disputes = Dispute.objects.filter(
        Q(opened_by=user) | Q(job__client=user) | Q(job__artisan=user)
    ).select_related('job')
    commissions = Commission.objects.filter(Q(job__client=user) | Q(job__artisan=user)).select_related('job')
    milestones = Milestone.objects.filter(escrow__in=escrows).select_related('escrow', 'escrow__job')

    context = {
        'escrows': escrows.order_by('-created_at')[:8],
        'invoices': invoices.order_by('-created_at')[:8],
        'payments': payments_qs.order_by('-created_at')[:8],
        'disputes': disputes.order_by('-created_at')[:6],
        'commissions': commissions.order_by('-created_at')[:6],
        'milestones': milestones.order_by('-created_at')[:6],
        'summary': {
            'escrow_total': escrows.count(),
            'invoice_total': invoices.count(),
            'payment_total': payments_qs.count(),
            'dispute_total': disputes.count(),
        },
    }
    return render(request, 'payments/payments.html', context)
