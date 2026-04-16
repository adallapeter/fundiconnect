# jobs/admin.py
from django.contrib import admin
from .models import Bid, BidNegotiation, Category, Job, JobContract, Reviews, SavedJob, Testimonials

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['title', 'client', 'budget', 'location', 'status', 'created_at']
    list_filter = ['status', 'category', 'urgency', 'created_at']
    search_fields = ['title', 'description', 'client__username', 'location']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ['job', 'artisan', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['job__title', 'artisan__user__username', 'message']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ['user', 'job', 'created_at']
    search_fields = ['user__username', 'job__title']
    readonly_fields = ['created_at']


@admin.register(BidNegotiation)
class BidNegotiationAdmin(admin.ModelAdmin):
    list_display = ['bid', 'sender', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['bid__job__title', 'sender__username', 'message']
    readonly_fields = ['created_at']


@admin.register(JobContract)
class JobContractAdmin(admin.ModelAdmin):
    list_display = ['job', 'client', 'artisan', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['job__title', 'client__username', 'artisan__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Reviews)
class ReviewsAdmin(admin.ModelAdmin):
    list_display = ['job', 'author', 'recipient', 'rating', 'review_type', 'created_at']
    list_filter = ['rating', 'review_type', 'created_at']
    search_fields = ['job__title', 'author__username', 'recipient__username', 'comment']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Testimonials)
class TestimonialsAdmin(admin.ModelAdmin):
    list_display = ['author', 'created_at']
    search_fields = ['author__username', 'content']
    readonly_fields = ['created_at']
