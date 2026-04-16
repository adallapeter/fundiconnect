from django.db import models
from django.utils import timezone
from users.models import CustomUser
from jobs.models import Job


class Escrow(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('funded', 'Funded'),
        ('released', 'Released'),
        ('refunded', 'Refunded'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
    )

    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='escrow')
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='escrows_as_client')
    artisan = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='escrows_as_artisan')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    funded_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Escrow for {self.job.title}'

    @property
    def status_badge_class(self):
        palette = {
            'pending': 'bg-amber-100 text-amber-700',
            'funded': 'bg-sky-100 text-sky-700',
            'released': 'bg-emerald-100 text-emerald-700',
            'refunded': 'bg-rose-100 text-rose-700',
            'disputed': 'bg-rose-100 text-rose-700',
            'cancelled': 'bg-slate-100 text-slate-600',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"


class Milestone(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('approved', 'Approved'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
    )

    escrow = models.ForeignKey(Escrow, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title} ({self.escrow.job.title})'

    @property
    def status_badge_class(self):
        palette = {
            'pending': 'bg-amber-100 text-amber-700',
            'in_progress': 'bg-sky-100 text-sky-700',
            'completed': 'bg-emerald-100 text-emerald-700',
            'approved': 'bg-green-100 text-green-700',
            'disputed': 'bg-rose-100 text-rose-700',
            'cancelled': 'bg-slate-100 text-slate-600',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"


class Invoice(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    )

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='invoices')
    issuer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='invoices_issued')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='invoices_received')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Invoice {self.id} for {self.job.title}'

    @property
    def status_badge_class(self):
        palette = {
            'draft': 'bg-slate-100 text-slate-700',
            'sent': 'bg-sky-100 text-sky-700',
            'paid': 'bg-emerald-100 text-emerald-700',
            'overdue': 'bg-rose-100 text-rose-700',
            'cancelled': 'bg-slate-100 text-slate-600',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"


class Payment(models.Model):
    METHOD_CHOICES = (
        ('card', 'Card'),
        ('wallet', 'Wallet'),
        ('bank', 'Bank Transfer'),
        ('mpesa', 'M-Pesa'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    payer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payments_made')
    payee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payments_received')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='KES')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='mpesa')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Payment {self.id} - {self.status}'

    @property
    def status_badge_class(self):
        palette = {
            'pending': 'bg-amber-100 text-amber-700',
            'completed': 'bg-emerald-100 text-emerald-700',
            'failed': 'bg-rose-100 text-rose-700',
            'refunded': 'bg-slate-100 text-slate-600',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"


class Dispute(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    )

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='disputes')
    opened_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='disputes_opened')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Dispute for {self.job.title}'

    @property
    def status_badge_class(self):
        palette = {
            'open': 'bg-amber-100 text-amber-700',
            'in_review': 'bg-sky-100 text-sky-700',
            'resolved': 'bg-emerald-100 text-emerald-700',
            'rejected': 'bg-rose-100 text-rose-700',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"


class Commission(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='commission')
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Commission for {self.job.title}'
