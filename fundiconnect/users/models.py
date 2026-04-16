from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django_otp import user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice
import uuid
from django.utils import timezone


# models.py
class CustomUser(AbstractUser):
    """
    A custom user model that extends Django's AbstractUser.
    This model uses a user_type field to differentiate between clients and artisans.
    """
    # Choices for the user type.
    USER_TYPE_CHOICES = (
        ('client', 'Client'),
        ('artisan', 'Artisan'),
    )
    user_type = models.CharField(max_length=7, choices=USER_TYPE_CHOICES, default='client')
    
    # Other profile fields.
    phone_number = models.CharField(max_length=15, unique=True, blank=True, null=True)
    profile_completed = models.BooleanField(default=False)
    
    # Verification fields
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    email_verification_code = models.CharField(max_length=6, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    email_verification_attempts = models.PositiveSmallIntegerField(default=0)
    email_verification_locked_until = models.DateTimeField(null=True, blank=True)
    phone_verification_code = models.CharField(max_length=6, blank=True, null=True)
    phone_verification_sent = models.DateTimeField(null=True, blank=True)
    phone_verification_skipped = models.BooleanField(default=False)
    
    # Properties to check the user type, which can be used in templates.
    # This keeps the logic consistent with your base.html template.
    @property
    def is_artisan(self):
        """Returns True if the user is an artisan."""
        return self.user_type == 'artisan'

    @property
    def is_client(self):
        """Returns True if the user is a client."""
        return self.user_type == 'client'
        
    def __str__(self):
        return self.username

    @property
    def display_name(self):
        if self.get_full_name():
            return self.get_full_name()
        if self.is_artisan and hasattr(self, 'artisan_profile') and self.artisan_profile.full_name:
            return self.artisan_profile.full_name
        if self.is_client and hasattr(self, 'client_profile') and self.client_profile.full_name:
            return self.client_profile.full_name
        return self.username

    @property
    def avatar(self):
        if self.is_artisan and hasattr(self, 'artisan_profile') and self.artisan_profile.profile_picture:
            return self.artisan_profile.profile_picture
        if self.is_client and hasattr(self, 'client_profile') and self.client_profile.profile_picture:
            return self.client_profile.profile_picture
        return None

    @property
    def two_factor_enabled(self):
        return user_has_device(self)
    
    def get_totp_device(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        try:
            return TOTPDevice.objects.get(user=self)
        except TOTPDevice.DoesNotExist:
            return None
    
    def generate_email_verification_token(self):
        self.email_verification_token = uuid.uuid4()
        # Use update() to avoid recursion and field validation issues
        CustomUser.objects.filter(id=self.id).update(
            email_verification_token=self.email_verification_token
        )
        return self.email_verification_token

    def generate_email_verification_code(self):
        import random
        code = f"{random.randint(0, 999999):06d}"
        now = timezone.now()
        self.email_verification_code = code
        self.email_verification_sent_at = now
        self.email_verification_attempts = 0
        self.email_verification_locked_until = None
        CustomUser.objects.filter(id=self.id).update(
            email_verification_code=code,
            email_verification_sent_at=now,
            email_verification_attempts=0,
            email_verification_locked_until=None,
        )
        return code

    def is_email_verification_locked(self):
        if not self.email_verification_locked_until:
            return False
        return timezone.now() < self.email_verification_locked_until

    def register_failed_email_attempt(self):
        attempts = (self.email_verification_attempts or 0) + 1
        locked_until = self.email_verification_locked_until
        if attempts >= 3:
            locked_until = timezone.now() + timezone.timedelta(days=1)
        CustomUser.objects.filter(id=self.id).update(
            email_verification_attempts=attempts,
            email_verification_locked_until=locked_until,
        )
        self.email_verification_attempts = attempts
        self.email_verification_locked_until = locked_until
        return locked_until
    
    def generate_phone_verification_code(self):
        import random
        self.phone_verification_code = str(random.randint(100000, 999999))
        self.phone_verification_sent = timezone.now()
        # Use update() to avoid recursion and field validation issues
        CustomUser.objects.filter(id=self.id).update(
            phone_verification_code=self.phone_verification_code,
            phone_verification_sent=self.phone_verification_sent
        )
        return self.phone_verification_code
    
    def verify_phone_code(self, code):
        if self.phone_verification_code == code:
            # Check if code is not expired (10 minutes)
            if self.phone_verification_sent and timezone.now() < self.phone_verification_sent + timezone.timedelta(minutes=10):
                self.phone_verified = True
                # Use update() to avoid recursion and field validation issues
                CustomUser.objects.filter(id=self.id).update(phone_verified=True, phone_verification_skipped=False)
                return True
        return False

    def needs_phone_verification(self):
        if self.phone_verification_skipped:
            return False
        if not self.phone_number:
            return False
        return not self.phone_verified
    
    def send_verification_email(self):
        from .notifications import send_email_verification

        code = self.generate_email_verification_code()
        return send_email_verification(self, code)
            

class ClientProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='client_profile')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    full_name = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    bio = models.TextField(blank=True)
    rating = models.FloatField(default=0.0)
    
    def __str__(self):
        return f"Client Profile - {self.user.username}"
    
    def is_complete(self):
        required_fields = ['address', 'city']
        for field in required_fields:
            if not getattr(self, field):
                return False
        return True

class ArtisanProfile(models.Model):
    
    """Extended profile information for artisans"""
    
    # Category options
    CATEGORY_CHOICES = (
        ('plumbing', 'Plumbing'),
        ('electrical', 'Electrical'),
        ('carpentry-joinery', 'Carpentry & Joinery'),
        ('painting-finishes', 'Painting & Finishes'),
        ('masonry-tiling', 'Masonry & Tiling'),
        ('welding-fabrication', 'Welding & Fabrication'),
        ('roofing-gutters', 'Roofing & Gutters'),
        ('flooring', 'Flooring'),
        ('appliance-repair', 'Appliance Repair'),
        ('hvac-refrigeration', 'HVAC & Refrigeration'),
        ('solar-backup-power', 'Solar & Backup Power'),
        ('cctv-security-systems', 'CCTV & Security Systems'),
        ('cleaning-sanitation', 'Cleaning & Sanitation'),
        ('moving-delivery-support', 'Moving & Delivery Support'),
        ('landscaping-gardening', 'Landscaping & Gardening'),
        ('water-systems-boreholes', 'Water Systems & Boreholes'),
        ('automotive-mechanics', 'Automotive Mechanics'),
        ('tailoring-fashion', 'Tailoring & Fashion'),
        ('beauty-grooming', 'Beauty & Grooming'),
        ('interior-design-decor', 'Interior Design & Decor'),
        ('other', 'Other'),
    )
    
    # Experience level
    EXPERIENCE_LEVELS = (
        ('beginner', 'Beginner (0-2 years)'),
        ('intermediate', 'Intermediate (2-5 years)'),
        ('expert', 'Expert (5+ years)'),
    )
    
    AVAILABILITY_CHOICES = (
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('unavailable', 'Unavailable'),
    )
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='artisan_profile')
    full_name = models.CharField(max_length=255)
    profile_picture = models.ImageField(upload_to='artisan_profiles/', blank=True, null=True)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    specialization = models.CharField(max_length=255, help_text="e.g., Residential Plumbing, Automotive Electrical, etc.")
    description = models.TextField(help_text="Describe your services and expertise")
    experience_level = models.CharField(max_length=15, choices=EXPERIENCE_LEVELS)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=200)
    availability = models.CharField(max_length=100, default="Available", help_text="e.g., Available Weekdays, Weekends Only, etc.", choices=AVAILABILITY_CHOICES)
    location = models.CharField(max_length=255, help_text="Your service area")
    country = models.CharField(max_length=100, default='Kenya')
    service_radius = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    portfolio_images = models.ManyToManyField('PortfolioImage', blank=True)
    certifications = models.ManyToManyField('Certification', blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    reviews = models.ManyToManyField('jobs.Reviews', blank=True)
    completed_projects = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profile_views = models.PositiveIntegerField(default=0)
    portfolio_views = models.PositiveIntegerField(default=0)
    verified_id = models.BooleanField(default=False)
    verified_portfolio = models.BooleanField(default=False)
    verified_skills = models.BooleanField(default=False)
    verified_certifications = models.BooleanField(default=False)
    verified_insurance = models.BooleanField(default=False)
    reputation_badges = models.ManyToManyField('ReputationBadge', blank=True, related_name='artisans')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.full_name} - {self.get_category_display()}"

    def get_experience_level_display(self):
        return dict(self.EXPERIENCE_LEVELS).get(self.experience_level, '')

    def get_availability_display(self):
        return dict(self.AVAILABILITY_CHOICES).get(self.availability, '')
    
    def average_rating(self):
        from jobs.models import Reviews
        """Calculate average rating from client reviews"""
        from django.db.models import Avg
        # Get reviews where artisan is the recipient (client to artisan reviews)
        reviews = Reviews.objects.filter(
            recipient=self.user, 
            review_type='client_to_artisan'
        )
        return reviews.aggregate(Avg('rating'))['rating__avg'] or 0

    def total_reviews(self):
        from jobs.models import Reviews
        """Count total reviews received"""
        return Reviews.objects.filter(
            recipient=self.user, 
            review_type='client_to_artisan'
        ).count()

    def get_recent_reviews(self, limit=5):
        from jobs.models import Reviews
        """Get recent reviews"""
        return Reviews.objects.filter(
            recipient=self.user, 
            review_type='client_to_artisan'
        ).order_by('-created_at')[:limit]

    @property
    def credibility_score(self):
        avg_rating = float(self.average_rating() or 0)
        review_count = self.total_reviews()
        project_score = min(self.completed_projects * 2.5, 25)
        review_score = min(review_count * 4, 25)
        rating_score = min(avg_rating * 10, 50)
        return round(rating_score + review_score + project_score, 1)

    @property
    def trust_score(self):
        trust = self.credibility_score
        trust += 5 if self.verified_id else 0
        trust += 5 if self.verified_portfolio else 0
        trust += 5 if self.verified_skills else 0
        trust += 3 if self.verified_certifications else 0
        trust += 2 if self.verified_insurance else 0
        return round(min(trust, 100), 1)

    def trust_badges(self):
        badges = []
        if self.verified_id:
            badges.append('ID Verified')
        if self.verified_portfolio:
            badges.append('Portfolio Verified')
        if self.verified_skills:
            badges.append('Skills Verified')
        if self.verified_certifications:
            badges.append('Certified')
        if self.verified_insurance:
            badges.append('Insured')
        return badges

    @property
    def two_factor_enabled(self):
        return user_has_device(self)
    
    def get_totp_device(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        try:
            return TOTPDevice.objects.get(user=self)
        except TOTPDevice.DoesNotExist:
            return None


class PortfolioImage(models.Model):
    """Portfolio images for artisans"""
    artisan = models.ForeignKey(ArtisanProfile, on_delete=models.CASCADE, related_name='portfolio')
    image = models.ImageField(upload_to='artisan_portfolio/')
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Portfolio image for {self.artisan.full_name}"


class Certification(models.Model):
    """Certifications for artisans"""
    name = models.CharField(max_length=255)
    issuing_organization = models.CharField(max_length=255)
    issue_date = models.DateField()
    expiration_date = models.DateField(blank=True, null=True)
    credential_id = models.CharField(max_length=255, blank=True)
    credential_url = models.URLField(blank=True)
    verified = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} from {self.issuing_organization}"


# models.py
from django.db import models
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class Conversation(models.Model):
    participants = models.ManyToManyField(CustomUser, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    job = models.ForeignKey('jobs.Job', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def get_other_user(self, user):
        return self.participants.exclude(id=user.id).first()

    def unread_count_for(self, user):
        return self.messages.exclude(sender=user).filter(is_read=False).count()

    def latest_message(self):
        return self.messages.order_by('-timestamp').first()

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'{self.sender.display_name}: {self.content[:40]}'


class MessageAttachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='message_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Attachment for {self.message.id}'


class ReputationBadge(models.Model):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=50, default='bi-award')

    def __str__(self):
        return self.name

class DirectHire(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='direct_hires_sent')
    artisan = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='direct_hires_received')
    job_title = models.CharField(max_length=255)
    description = models.TextField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    deadline = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Direct hire: {self.job_title} - {self.get_status_display()}"

    @property
    def status_badge_class(self):
        palette = {
            'pending': 'bg-amber-100 text-amber-700',
            'accepted': 'bg-emerald-100 text-emerald-700',
            'rejected': 'bg-rose-100 text-rose-700',
            'completed': 'bg-green-100 text-green-700',
            'cancelled': 'bg-slate-100 text-slate-600',
        }
        return f"rounded-full px-3 py-1 text-xs font-semibold {palette.get(self.status, 'bg-slate-100 text-slate-600')}"


class Notification(models.Model):
    LEVEL_CHOICES = (
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('urgent', 'Urgent'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    body = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='info')
    action_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.display_name} - {self.title}'

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read', 'updated_at'])


class AssistantChat(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assistant_chats')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user.display_name} [{self.role}]'
