from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from users.chat_utils import add_system_style_message, get_or_create_conversation_for_users
from users.models import ArtisanProfile, CustomUser

from .forms import BidForm, JobForm, ReviewForm
from .models import Bid, BidNegotiation, Category, Job, JobContract, Reviews, SavedJob, Testimonials
from .seed_data import seed_job_categories


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _ensure_categories_seeded():
    if not Category.objects.exists():
        seed_job_categories()


def _serialize_job(job):
    return {
        'id': job.id,
        'title': job.title,
        'status': job.get_status_display(),
        'budget': f'{job.budget:,.0f}',
        'location': job.location,
        'bids_count': job.bids.count(),
        'updated_at': timezone.localtime(job.updated_at).strftime('%b %d, %Y %I:%M %p'),
    }


def _dashboard_stats_for_client(user):
    jobs = Job.objects.filter(client=user)
    return {
        'posted_jobs': jobs.count(),
        'open_jobs': jobs.filter(status='open').count(),
        'in_progress_jobs': jobs.filter(status='in_progress').count(),
        'completed_jobs': jobs.filter(status='completed').count(),
    }


def _dashboard_stats_for_artisan(artisan_profile):
    bids = Bid.objects.filter(artisan=artisan_profile)
    return {
        'bids_sent': bids.count(),
        'accepted_bids': bids.filter(status='accepted').count(),
        'pending_bids': bids.filter(status='pending').count(),
        'completed_jobs': Job.objects.filter(
            bids__artisan=artisan_profile,
            bids__status='accepted',
            status='completed',
        ).distinct().count(),
    }


def _marketplace_satisfaction_snapshot():
    review_qs = Reviews.objects.filter(review_type='client_to_artisan')
    total_reviews = review_qs.count()
    average_rating = float(review_qs.aggregate(avg=Avg('rating'))['avg'] or 0)
    positive_reviews = review_qs.filter(rating__gte=4).count()
    positive_ratio = (positive_reviews / total_reviews) if total_reviews else 0
    satisfaction_rate = int(round(((average_rating / 5.0) * 0.6 + positive_ratio * 0.4) * 100)) if total_reviews else 0

    return {
        'total_reviews': total_reviews,
        'average_rating': round(average_rating, 1),
        'satisfaction_rate': satisfaction_rate,
        'positive_ratio': int(round(positive_ratio * 100)) if total_reviews else 0,
    }


def home(request):
    _ensure_categories_seeded()
    categories = Category.objects.annotate(open_jobs=Count('job', filter=Q(job__status='open')))
    featured_artisans = ArtisanProfile.objects.filter(availability='available').order_by('-rating', '-completed_projects')[:4]
    recent_jobs = Job.objects.filter(status='open').select_related('category', 'client').order_by('-created_at')[:6]
    success_stories = Reviews.objects.select_related('author', 'recipient', 'job').filter(rating__gte=4).order_by('-created_at')[:4]
    testimonials = Testimonials.objects.select_related('author').order_by('-created_at')[:4]
    satisfaction = _marketplace_satisfaction_snapshot()
    verified_artisans = ArtisanProfile.objects.filter(
        Q(verified_id=True)
        | Q(verified_portfolio=True)
        | Q(verified_skills=True)
        | Q(verified_certifications=True)
        | Q(verified_insurance=True)
    ).count()
    open_jobs_count = Job.objects.filter(status='open').count()

    context = {
        'stats': {
            'active_artisans': ArtisanProfile.objects.filter(availability='available').count(),
            'verified_artisans': verified_artisans,
            'completed_projects': Job.objects.filter(status='completed').count(),
            'completed_month': Job.objects.filter(status='completed', updated_at__month=timezone.now().month, updated_at__year=timezone.now().year).count(),
            'open_jobs': open_jobs_count,
            'satisfaction_rate': satisfaction['satisfaction_rate'],
            'average_rating': satisfaction['average_rating'],
            'total_reviews': satisfaction['total_reviews'],
            'positive_ratio': satisfaction['positive_ratio'],
            'avg_response_time': 12,
            'updated_at': timezone.localtime(timezone.now()).strftime('%b %d, %Y %I:%M %p'),
        },
        'categories': categories,
        'featured_artisans': featured_artisans,
        'recent_jobs': recent_jobs,
        'success_stories': success_stories,
        'testimonials': testimonials,
        'home_mode': 'guest',
    }

    if request.user.is_authenticated:
        if request.user.is_client:
            client_jobs = Job.objects.filter(client=request.user).select_related('category').order_by('-updated_at')
            context.update(
                {
                    'home_mode': 'client',
                    'primary_stat_label': 'Your open jobs',
                    'primary_stat_value': client_jobs.filter(status='open').count(),
                    'personal_stats': {
                        'open_jobs': client_jobs.filter(status='open').count(),
                        'active_jobs': client_jobs.filter(status='in_progress').count(),
                        'completed_jobs': client_jobs.filter(status='completed').count(),
                    },
                    'personal_jobs': client_jobs[:4],
                    'recommended_artisans': ArtisanProfile.objects.filter(availability='available').order_by('-rating', '-completed_projects')[:4],
                }
            )
        elif request.user.is_artisan and hasattr(request.user, 'artisan_profile'):
            artisan_profile = request.user.artisan_profile
            open_matches = (
                Job.objects.filter(status='open')
                .exclude(bids__artisan=artisan_profile)
                .select_related('category', 'client')
                .order_by('-created_at')
            )
            if artisan_profile.category:
                open_matches = open_matches.filter(
                    Q(category__slug__iexact=artisan_profile.category)
                    | Q(category__name__iexact=artisan_profile.get_category_display())
                )
            context.update(
                {
                    'home_mode': 'artisan',
                    'primary_stat_label': 'Pending bids',
                    'primary_stat_value': Bid.objects.filter(artisan=artisan_profile, status='pending').count(),
                    'personal_stats': _dashboard_stats_for_artisan(artisan_profile),
                    'personal_jobs': open_matches[:4],
                    'my_active_jobs': Job.objects.filter(
                        artisan=request.user,
                        status='in_progress',
                    ).select_related('category')[:4],
                }
            )

    return render(request, 'jobs/home.html', context)


def job_list(request):
    _ensure_categories_seeded()
    jobs = (
        Job.objects.select_related('client', 'artisan', 'category')
        .prefetch_related(Prefetch('bids', queryset=Bid.objects.select_related('artisan__user').order_by('-created_at')))
        .order_by('-updated_at')
    )
    categories = Category.objects.all().order_by('name')
    view_type = 'public'
    stats = {}

    if request.user.is_authenticated and request.user.is_client:
        view_type = 'client_management'
        jobs = jobs.filter(client=request.user)
        stats = _dashboard_stats_for_client(request.user)
    elif request.user.is_authenticated and request.user.is_artisan:
        view_type = 'artisan_management'
        artisan_profile = request.user.artisan_profile
        tab = request.GET.get('tab', 'available')

        if tab == 'available':
            jobs = jobs.filter(status='open').exclude(bids__artisan=artisan_profile)
        elif tab == 'active':
            jobs = jobs.filter(status='in_progress', bids__artisan=artisan_profile, bids__status='accepted').distinct()
        elif tab == 'completed':
            jobs = jobs.filter(status='completed', bids__artisan=artisan_profile, bids__status='accepted').distinct()
        else:
            jobs = jobs.filter(bids__artisan=artisan_profile).distinct()

        stats = _dashboard_stats_for_artisan(artisan_profile)

    if request.user.is_authenticated and request.GET.get('saved') == '1':
        jobs = jobs.filter(saved_by__user=request.user)
        view_type = 'saved_jobs'

    status_filter = request.GET.get('status')
    if status_filter:
        jobs = jobs.filter(status=status_filter)

    category_filter = request.GET.get('category')
    active_category = None
    if category_filter:
        jobs = jobs.filter(category_id=category_filter)
        active_category = Category.objects.filter(id=category_filter).first()

    budget_filter = request.GET.get('budget')
    if budget_filter == 'low':
        jobs = jobs.filter(budget__lt=5000)
    elif budget_filter == 'medium':
        jobs = jobs.filter(budget__gte=5000, budget__lte=20000)
    elif budget_filter == 'high':
        jobs = jobs.filter(budget__gt=20000)

    location_filter = request.GET.get('location')
    if location_filter:
        jobs = jobs.filter(location__icontains=location_filter)

    search_query = request.GET.get('q')
    if search_query:
        jobs = jobs.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(location__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    saved_ids = list(SavedJob.objects.filter(user=request.user).values_list('job_id', flat=True)) if request.user.is_authenticated else []

    if _is_ajax(request):
        html = render_to_string(
            'partials/job_cards.html',
            {'jobs': jobs, 'request': request, 'saved_ids': saved_ids},
            request=request,
        )
        return JsonResponse({'html': html, 'count': jobs.count()})

    return render(
        request,
        'jobs/job_list.html',
        {
            'jobs': jobs,
            'categories': categories,
            'active_category': active_category,
            'stats': stats,
            'view_type': view_type,
            'saved_ids': saved_ids,
        },
    )


@login_required
def publish_job(request, job_id):
    job = get_object_or_404(Job, id=job_id, client=request.user)
    if job.status == 'draft':
        job.status = 'open'
        job.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Job published successfully.')
    else:
        messages.warning(request, 'Only draft jobs can be published.')
    return redirect('job_detail', job_id=job.id)


@login_required
def complete_job(request, job_id):
    job = get_object_or_404(Job, id=job_id, client=request.user)
    if job.status == 'in_progress':
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at', 'updated_at'])
        if _is_ajax(request):
            return JsonResponse({'success': True, 'status': job.get_status_display(), 'status_key': job.status, 'message': 'Job marked as completed.'})
        messages.success(request, 'Job marked as completed.')
    else:
        if _is_ajax(request):
            return JsonResponse({'success': False, 'message': 'Only jobs in progress can be completed.'}, status=400)
        messages.warning(request, 'Only jobs in progress can be completed.')
    return redirect('job_detail', job_id=job.id)


@login_required
def post_job(request):
    _ensure_categories_seeded()
    if request.method == 'POST':
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.client = request.user
            job.status = 'open'
            job.save()
            form.save_m2m()
            messages.success(request, 'Job posted successfully.')
            return redirect('job_detail', job_id=job.id)
    else:
        form = JobForm()

    return render(request, 'jobs/post_job.html', {'form': form, 'skills': [], 'categories': Category.objects.all().order_by('name')})


@login_required
def edit_job(request, job_id):
    _ensure_categories_seeded()
    job = get_object_or_404(Job, id=job_id, client=request.user)

    if request.method == 'POST':
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job updated successfully.')
            return redirect('job_detail', job_id=job.id)
    else:
        form = JobForm(instance=job)

    return render(request, 'jobs/edit_job.html', {'form': form, 'job': job, 'skills': [], 'categories': Category.objects.all().order_by('name')})


@login_required
def job_detail(request, job_id):
    job = get_object_or_404(
        Job.objects.select_related('client', 'artisan', 'category').prefetch_related(
            Prefetch('bids', queryset=Bid.objects.select_related('artisan__user').order_by('-created_at')),
            Prefetch('reviews', queryset=Reviews.objects.select_related('author', 'recipient').order_by('-created_at')),
        ),
        id=job_id,
    )

    user_bid = None
    if request.user.is_authenticated and request.user.is_artisan and hasattr(request.user, 'artisan_profile'):
        user_bid = job.bids.filter(artisan=request.user.artisan_profile).first()

    accepted_bid = job.accepted_bid
    saved = False
    if request.user.is_authenticated:
        saved = SavedJob.objects.filter(user=request.user, job=job).exists()
    negotiations = BidNegotiation.objects.filter(bid__job=job).select_related('sender', 'bid').order_by('-created_at')
    context = {
        'job': job,
        'bids': job.bids.all(),
        'user_bid': user_bid,
        'accepted_bid': accepted_bid,
        'saved': saved,
        'negotiations': negotiations,
        'client_review': job.get_client_review(),
        'artisan_review': job.get_artisan_review(),
        'bid_form': BidForm(),
        'review_form': ReviewForm(),
    }
    return render(request, 'jobs/job_detail.html', context)


@login_required
def submit_review(request, job_id, review_type):
    job = get_object_or_404(Job, id=job_id)
    if review_type not in ['client_to_artisan', 'artisan_to_client'] or not job.can_be_reviewed_by(request.user):
        messages.error(request, 'You cannot review this job yet.')
        return redirect('job_detail', job_id=job.id)

    recipient = job.artisan if review_type == 'client_to_artisan' else job.client
    if Reviews.objects.filter(job=job, author=request.user, review_type=review_type).exists():
        messages.info(request, 'You have already submitted this review.')
        return redirect('job_detail', job_id=job.id)

    form = ReviewForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        review = form.save(commit=False)
        review.job = job
        review.author = request.user
        review.recipient = recipient
        review.review_type = review_type
        review.save()
        messages.success(request, 'Review submitted successfully.')
        return redirect('job_detail', job_id=job.id)

    return render(request, 'jobs/submit_review.html', {'form': form, 'job': job, 'review_type': review_type, 'recipient': recipient})


@login_required
def review_list(request, user_id=None):
    profile_user = get_object_or_404(CustomUser, id=user_id) if user_id else request.user
    return render(
        request,
        'jobs/review_list.html',
        {
            'profile_user': profile_user,
            'received_reviews': Reviews.objects.filter(recipient=profile_user).select_related('author', 'job'),
            'authored_reviews': Reviews.objects.filter(author=profile_user).select_related('recipient', 'job'),
        },
    )


@login_required
def close_job(request, job_id):
    job = get_object_or_404(Job, id=job_id, client=request.user)
    if job.status in ['open', 'draft']:
        job.status = 'closed'
        job.save(update_fields=['status', 'updated_at'])
        if _is_ajax(request):
            return JsonResponse({'success': True, 'status': job.get_status_display(), 'status_key': job.status, 'message': 'Job closed successfully.'})
        messages.success(request, 'Job closed successfully.')
    else:
        if _is_ajax(request):
            return JsonResponse({'success': False, 'message': 'This job cannot be closed right now.'}, status=400)
        messages.warning(request, 'This job cannot be closed right now.')
    return redirect('job_detail', job_id=job.id)


@login_required
def reopen_job(request, job_id):
    job = get_object_or_404(Job, id=job_id, client=request.user)
    if job.can_be_reopened():
        job.status = 'open'
        job.completed_at = None
        job.save(update_fields=['status', 'completed_at', 'updated_at'])
        if _is_ajax(request):
            return JsonResponse({'success': True, 'status': job.get_status_display(), 'status_key': job.status, 'message': 'Job reopened successfully.'})
        messages.success(request, 'Job reopened successfully.')
    else:
        if _is_ajax(request):
            return JsonResponse({'success': False, 'message': 'This job cannot be reopened.'}, status=400)
        messages.warning(request, 'This job cannot be reopened.')
    return redirect('job_detail', job_id=job.id)


@login_required
def place_bid(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    if not request.user.is_artisan:
        messages.error(request, 'Only artisans can place bids.')
        return redirect('job_detail', job_id=job.id)

    if job.status != 'open':
        messages.error(request, 'This job is no longer accepting bids.')
        return redirect('job_detail', job_id=job.id)

    artisan_profile = request.user.artisan_profile
    existing_bid = Bid.objects.filter(job=job, artisan=artisan_profile).first()
    form = BidForm(request.POST or None, instance=existing_bid)

    if request.method == 'POST' and form.is_valid():
        bid = form.save(commit=False)
        bid.job = job
        bid.artisan = artisan_profile
        bid.status = 'pending'
        bid.save()

        if _is_ajax(request):
            bid_card = render_to_string('partials/bid_card.html', {'bid': bid, 'job': job, 'request': request}, request=request)
            return JsonResponse({'success': True, 'message': 'Bid submitted successfully.', 'bid_html': bid_card})

        messages.success(request, 'Bid submitted successfully.')
        return redirect('job_detail', job_id=job.id)

    if _is_ajax(request) and request.method == 'POST':
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    return render(request, 'jobs/place_bid.html', {'job': job, 'form': form})


@login_required
def accept_bid(request, bid_id):
    bid = get_object_or_404(Bid.objects.select_related('job', 'artisan__user'), id=bid_id)
    job = bid.job
    if job.client != request.user:
        messages.error(request, "You don't have permission to accept bids for this job.")
        return redirect('job_detail', job_id=job.id)

    if job.status != 'open':
        messages.warning(request, 'This job is no longer accepting bids.')
        return redirect('job_detail', job_id=job.id)

    Bid.objects.filter(job=job, status='accepted').update(status='rejected')
    bid.status = 'accepted'
    bid.save(update_fields=['status', 'updated_at'])
    Bid.objects.filter(job=job).exclude(id=bid.id).exclude(status='withdrawn').update(status='rejected')
    job.status = 'in_progress'
    job.artisan = bid.artisan.user
    job.save(update_fields=['status', 'artisan', 'updated_at'])
    JobContract.objects.get_or_create(
        job=job,
        defaults={
            'client': job.client,
            'artisan': bid.artisan.user,
            'template_body': f'Contract for {job.title}. Scope: {job.description}',
        },
    )
    conversation, created = get_or_create_conversation_for_users(job.client, bid.artisan.user, job=job)
    if created:
        add_system_style_message(
            conversation,
            job.client,
            f'Your bid for "{job.title}" has been accepted. Let us use this thread to coordinate delivery details.',
        )

    if _is_ajax(request):
        return JsonResponse({'success': True, 'message': f'{bid.artisan.user.display_name} is now assigned.', 'job': _serialize_job(job)})

    messages.success(request, f"You accepted {bid.artisan.user.display_name}'s bid.")
    return redirect('job_detail', job_id=job.id)


@login_required
def save_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    SavedJob.objects.get_or_create(user=request.user, job=job)
    if _is_ajax(request):
        return JsonResponse({'success': True, 'saved': True})
    messages.success(request, 'Job saved to your favorites.')
    return redirect('job_detail', job_id=job.id)


@login_required
def unsave_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    SavedJob.objects.filter(user=request.user, job=job).delete()
    if _is_ajax(request):
        return JsonResponse({'success': True, 'saved': False})
    messages.info(request, 'Job removed from saved list.')
    return redirect('job_detail', job_id=job.id)


@login_required
def counter_bid(request, bid_id):
    bid = get_object_or_404(Bid.objects.select_related('job', 'artisan__user'), id=bid_id)
    job = bid.job
    if job.client != request.user:
        messages.error(request, "You don't have permission to counter this bid.")
        return redirect('job_detail', job_id=job.id)

    proposed_amount = request.POST.get('amount')
    proposed_timeline = request.POST.get('timeline', '')
    message_text = request.POST.get('message', '').strip()

    if not message_text:
        messages.warning(request, 'Please include a counter message.')
        return redirect('job_detail', job_id=job.id)

    bid.status = 'countered'
    bid.save(update_fields=['status', 'updated_at'])
    BidNegotiation.objects.create(
        bid=bid,
        sender=request.user,
        message=message_text,
        proposed_amount=proposed_amount or None,
        proposed_timeline=proposed_timeline,
    )
    messages.success(request, 'Counter proposal sent.')
    return redirect('job_detail', job_id=job.id)


@login_required
def respond_counter_bid(request, bid_id):
    if not request.user.is_artisan:
        messages.error(request, 'Only artisans can respond to counter proposals.')
        return redirect('home')
    if request.method != 'POST':
        return redirect('artisan_bid_detail', bid_id=bid_id)

    bid = get_object_or_404(
        Bid.objects.select_related('job', 'artisan__user'),
        id=bid_id,
        artisan=request.user.artisan_profile,
    )
    if bid.status != 'countered':
        messages.warning(request, 'This bid has no active counter proposal.')
        return redirect('artisan_bid_detail', bid_id=bid.id)

    negotiation = bid.negotiations.order_by('-created_at').first()
    if not negotiation:
        messages.warning(request, 'No counter proposal found for this bid.')
        return redirect('artisan_bid_detail', bid_id=bid.id)

    action = request.POST.get('action')
    if action == 'accept':
        if negotiation.proposed_amount:
            bid.amount = negotiation.proposed_amount
        bid.status = 'accepted'
        bid.save(update_fields=['amount', 'status', 'updated_at'])
        negotiation.status = 'accepted'
        negotiation.save(update_fields=['status'])

        job = bid.job
        Bid.objects.filter(job=job, status='accepted').exclude(id=bid.id).update(status='rejected')
        Bid.objects.filter(job=job).exclude(id=bid.id).exclude(status='withdrawn').update(status='rejected')
        job.status = 'in_progress'
        job.artisan = bid.artisan.user
        job.save(update_fields=['status', 'artisan', 'updated_at'])
        JobContract.objects.get_or_create(
            job=job,
            defaults={
                'client': job.client,
                'artisan': bid.artisan.user,
                'template_body': f'Contract for {job.title}. Scope: {job.description}',
            },
        )

        conversation, created = get_or_create_conversation_for_users(job.client, bid.artisan.user, job=job)
        if created:
            add_system_style_message(
                conversation,
                job.client,
                f'Your bid for "{job.title}" has been accepted after a counter proposal.',
            )
        messages.success(request, 'Counter proposal accepted. The job is now in progress.')
        return redirect('job_detail', job_id=job.id)

    if action == 'reject':
        bid.status = 'rejected'
        bid.save(update_fields=['status', 'updated_at'])
        negotiation.status = 'rejected'
        negotiation.save(update_fields=['status'])
        messages.info(request, 'Counter proposal declined.')
        return redirect('artisan_bid_detail', bid_id=bid.id)

    messages.warning(request, 'Invalid counter response action.')
    return redirect('artisan_bid_detail', bid_id=bid.id)


@login_required
def reject_bid(request, bid_id):
    bid = get_object_or_404(Bid.objects.select_related('job', 'artisan__user'), id=bid_id)
    if bid.job.client != request.user:
        messages.error(request, "You don't have permission to reject bids for this job.")
        return redirect('job_detail', job_id=bid.job.id)

    bid.status = 'rejected'
    bid.save(update_fields=['status', 'updated_at'])

    if _is_ajax(request):
        return JsonResponse({'success': True, 'message': f'{bid.artisan.user.display_name} was declined.'})

    messages.success(request, f"You rejected {bid.artisan.user.display_name}'s bid.")
    return redirect('job_detail', job_id=bid.job.id)


@login_required
def withdraw_bid(request, bid_id):
    bid = get_object_or_404(Bid.objects.select_related('job', 'artisan__user'), id=bid_id)
    if bid.artisan.user != request.user:
        messages.error(request, "You don't have permission to withdraw this bid.")
        return redirect('job_detail', job_id=bid.job.id)

    if bid.status != 'pending':
        messages.warning(request, 'This bid can no longer be withdrawn.')
        return redirect('job_detail', job_id=bid.job.id)

    bid.status = 'withdrawn'
    bid.save(update_fields=['status', 'updated_at'])

    if _is_ajax(request):
        return JsonResponse({'success': True, 'message': 'Bid withdrawn.'})

    messages.success(request, 'Bid withdrawn successfully.')
    return redirect('job_detail', job_id=bid.job.id)


@login_required
def edit_bid(request, bid_id):
    bid = get_object_or_404(Bid.objects.select_related('job', 'artisan__user'), id=bid_id, artisan=request.user.artisan_profile)
    if bid.status != 'pending':
        messages.warning(request, 'Only pending bids can be edited.')
        return redirect('job_detail', job_id=bid.job.id)

    form = BidForm(request.POST or None, instance=bid)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Bid updated successfully.')
        return redirect('job_detail', job_id=bid.job.id)

    return render(request, 'jobs/edit_bid.html', {'form': form, 'bid': bid, 'job': bid.job})


def category_list(request):
    _ensure_categories_seeded()
    categories = Category.objects.annotate(open_jobs=Count('job', filter=Q(job__status='open'))).order_by('name')
    return render(request, 'jobs/category_list.html', {'categories': categories})


@login_required
def category_detail(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug)
    artisans = ArtisanProfile.objects.filter(category__iexact=category.slug, availability='available').order_by('-rating', '-completed_projects')
    return render(request, 'jobs/category_detail.html', {'category': category, 'artisans': artisans})


def search_artisans(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug)
    query = request.GET.get('q', '')
    artisans = ArtisanProfile.objects.filter(category__iexact=category.slug, availability='available')
    if query:
        artisans = artisans.filter(
            Q(full_name__icontains=query)
            | Q(description__icontains=query)
            | Q(location__icontains=query)
            | Q(specialization__icontains=query)
        )
    return render(request, 'jobs/category_detail.html', {'category': category, 'artisans': artisans, 'query': query})


def testimonial_list(request):
    return render(request, 'jobs/testimonial_list.html', {'testimonials': Testimonials.objects.select_related('author').order_by('-created_at')})


@login_required
def artisan_bids(request):
    if not request.user.is_artisan:
        messages.error(request, 'Only artisans can access this page.')
        return redirect('home')

    artisan = request.user.artisan_profile
    bids = Bid.objects.filter(artisan=artisan).select_related('job', 'job__client', 'job__category').order_by('-created_at')

    status_filter = request.GET.get('status')
    if status_filter:
        bids = bids.filter(status=status_filter)

    search_query = request.GET.get('q')
    if search_query:
        bids = bids.filter(Q(job__title__icontains=search_query) | Q(job__location__icontains=search_query))

    bid_stats = {
        'total': Bid.objects.filter(artisan=artisan).count(),
        'pending': Bid.objects.filter(artisan=artisan, status='pending').count(),
        'accepted': Bid.objects.filter(artisan=artisan, status='accepted').count(),
        'countered': Bid.objects.filter(artisan=artisan, status='countered').count(),
        'rejected': Bid.objects.filter(artisan=artisan, status='rejected').count(),
        'withdrawn': Bid.objects.filter(artisan=artisan, status='withdrawn').count(),
        'expired': Bid.objects.filter(artisan=artisan, status='expired').count(),
    }
    return render(request, 'jobs/artisan_bids.html', {'bids': bids, 'bid_stats': bid_stats, 'status_filter': status_filter, 'search_query': search_query or ''})


@login_required
def artisan_bid_detail(request, bid_id):
    bid = get_object_or_404(Bid.objects.select_related('job', 'job__client', 'job__category', 'artisan__user'), id=bid_id, artisan=request.user.artisan_profile)
    suggested_jobs = None
    if bid.status in ['rejected', 'withdrawn']:
        suggested_jobs = Job.objects.filter(category=bid.job.category, status='open').exclude(bids__artisan=request.user.artisan_profile)[:4]
    negotiations = bid.negotiations.select_related('sender').order_by('-created_at')
    latest_negotiation = negotiations.first() if bid.status == 'countered' else None
    return render(
        request,
        'jobs/artisan_bid_detail.html',
        {
            'bid': bid,
            'suggested_jobs': suggested_jobs,
            'negotiations': negotiations,
            'latest_negotiation': latest_negotiation,
        },
    )
