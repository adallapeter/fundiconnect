# jobs/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from users.models import ArtisanProfile, CustomUser
from django.core.validators import MinValueValidator, MaxValueValidator

class Job(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )
    
    URGENCY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    DURATION_CHOICES = (
        ('less_than_day', 'Less than a day'),
        ('1-3_days', '1-3 days'),
        ('3-7_days', '3-7 days'),
        ('1-2_weeks', '1-2 weeks'),
        ('more_than_2_weeks', 'More than 2 weeks'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='posted_jobs')
    artisan = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='assigned_jobs')
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES, null=True, blank=True)
    skills_required = models.ManyToManyField('Skill', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.title
    
    def get_bids_count(self):
        return self.bids.count()
    
    def get_pending_bids_count(self):
        return self.bids.filter(status='pending').count()
    
    def get_accepted_bids_count(self):
        return self.bids.filter(status='accepted').count()

    def get_rejected_bids_count(self):
        return self.bids.filter(status='rejected').count()

    @property
    def status_color(self):
        palette = {
            'draft': 'slate-100 text-slate-700',
            'open': 'emerald-100 text-emerald-700',
            'in_progress': 'sky-100 text-sky-700',
            'completed': 'green-100 text-green-700',
            'closed': 'slate-200 text-slate-700',
            'expired': 'rose-100 text-rose-700',
            'cancelled': 'amber-100 text-amber-700',
        }
        return palette.get(self.status, 'slate-100 text-slate-700')

    @property
    def status_badge_class(self):
        base = self.status_color
        return f'rounded-full px-3 py-1 text-xs font-semibold {base}'

    @property
    def state_badge_label(self):
        return 'Current' if self.status in {'open', 'in_progress'} else 'Past'

    @property
    def state_badge_class(self):
        return 'bg-sky-50 text-sky-700' if self.status in {'open', 'in_progress'} else 'bg-slate-100 text-slate-600'
    
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status.capitalize())
    
    def get_category_display(self):
        return self.category.name if self.category else 'Uncategorized'

    def get_recent_bids(self, limit=5):
        return self.bids.select_related('artisan', 'artisan__artisanprofile').order_by('-created_at')[:limit]
    
    def is_assignable(self):
        return self.status == 'open' and self.is_active
    
    def can_be_completed(self):
        return self.status == 'in_progress'
    
    def can_be_reopened(self):
        return self.status in ['closed', 'completed'] and self.is_active
    
    def can_be_reviewed_by(self, user):
        """Check if user can review this job"""
        if self.status != 'closed':
            return False
            
        if user == self.client:
            return not self.reviews.filter(author=user, review_type='client_to_artisan').exists()
            
        if user == self.artisan:
            return not self.reviews.filter(author=user, review_type='artisan_to_client').exists()
            
        return False

    def get_client_review(self):
        return self.reviews.filter(review_type='client_to_artisan').first()

    def get_artisan_review(self):
        return self.reviews.filter(review_type='artisan_to_client').first()

    def has_both_reviews(self):
        return self.reviews.filter(review_type='client_to_artisan').exists() and \
            self.reviews.filter(review_type='artisan_to_client').exists()

    @property
    def accepted_bid(self):
        return self.bids.filter(status='accepted').first()


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class")
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Skill(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='skills')
    
    def __str__(self):
        return self.name

class JobImage(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='job_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for {self.job.title}"

class Bid(models.Model):
    BID_STATUS = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('countered', 'Countered'),
        ('expired', 'Expired'),
    )
    
    COMPLETION_TIME = (
        ('1', 'Within 1 day'),
        ('3', 'Within 3 days'),
        ('7', 'Within 1 week'),
        ('14', 'Within 2 weeks'),
        ('30', 'Within 1 month'),
    )
    
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='bids')
    artisan = models.ForeignKey(ArtisanProfile, on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField()
    completion_time = models.CharField(max_length=20, choices=COMPLETION_TIME)
    status = models.CharField(max_length=20, choices=BID_STATUS, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('job', 'artisan')
    
    def __str__(self):
        return f"{self.artisan.user.get_full_name()} - {self.job.title}"
    
    def get_completion_time_display(self):
        return dict(self.COMPLETION_TIME).get(self.completion_time, '')

    @property
    def status_badge_class(self):
        palette = {
            'pending': 'bg-amber-100 text-amber-700',
            'accepted': 'bg-emerald-100 text-emerald-700',
            'rejected': 'bg-rose-100 text-rose-700',
            'withdrawn': 'bg-slate-100 text-slate-600',
            'countered': 'bg-sky-100 text-sky-700',
            'expired': 'bg-rose-100 text-rose-700',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"


class BidNegotiation(models.Model):
    STATUS_CHOICES = (
        ('proposed', 'Proposed'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('withdrawn', 'Withdrawn'),
    )

    bid = models.ForeignKey(Bid, on_delete=models.CASCADE, related_name='negotiations')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()
    proposed_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    proposed_timeline = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='proposed')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Negotiation for {self.bid.job.title} by {self.sender.display_name}'

    @property
    def status_badge_class(self):
        palette = {
            'proposed': 'bg-amber-100 text-amber-700',
            'accepted': 'bg-emerald-100 text-emerald-700',
            'rejected': 'bg-rose-100 text-rose-700',
            'expired': 'bg-rose-100 text-rose-700',
            'withdrawn': 'bg-slate-100 text-slate-600',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"


class SavedJob(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'job')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.display_name} saved {self.job.title}'


class JobContract(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('signed', 'Signed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )

    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='contract')
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contracts_as_client')
    artisan = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contracts_as_artisan')
    template_body = models.TextField()
    signed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Contract for {self.job.title}'

    @property
    def status_badge_class(self):
        palette = {
            'draft': 'bg-slate-100 text-slate-700',
            'signed': 'bg-emerald-100 text-emerald-700',
            'in_progress': 'bg-sky-100 text-sky-700',
            'completed': 'bg-green-100 text-green-700',
            'cancelled': 'bg-amber-100 text-amber-700',
            'expired': 'bg-rose-100 text-rose-700',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"

    

class Reviews(models.Model):
    REVIEW_TYPE_CHOICES = (
        ('client_to_artisan', 'Client to Artisan'),
        ('artisan_to_client', 'Artisan to Client'),
    )
    
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='reviews')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='authored_reviews')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_reviews', blank=True, null=True)
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPE_CHOICES, blank=True, null=True)
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (worst) to 5 (best)"
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['job', 'author', 'review_type']
        ordering = ['-created_at']

    def __str__(self):
        return f'Review by {self.author.username} for {self.recipient.username} - {self.rating} stars'

class Testimonials(models.Model):
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Testimonial by {self.author.username}'
