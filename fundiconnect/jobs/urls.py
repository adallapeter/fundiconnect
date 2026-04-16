# jobs/urls.py
from django.urls import path
from . import views
from django.contrib.auth.decorators import login_required



# jobs/urls.py
urlpatterns = [
    path('home/', views.home, name='home'),
    path('jobs/', views.job_list, name='job_list'),
    path('post_job/', views.post_job, name='post_job'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('edit_job/<int:job_id>/', views.edit_job, name='edit_job'),
    path('job/<int:job_id>/close/', views.close_job, name='close_job'),
    path('job/<int:job_id>/reopen/', views.reopen_job, name='reopen_job'),
    path('job/<int:job_id>/complete/', views.complete_job, name='complete_job'),
    path('job/<int:job_id>/publish/', views.publish_job, name='publish_job'),
    path('job/<int:job_id>/bid/', views.place_bid, name='place_bid'),
    path('job/<int:job_id>/save/', views.save_job, name='save_job'),
    path('job/<int:job_id>/unsave/', views.unsave_job, name='unsave_job'),
    path('bid/<int:bid_id>/accept/', views.accept_bid, name='accept_bid'),
    path('bid/<int:bid_id>/reject/', views.reject_bid, name='reject_bid'),
    path('bid/<int:bid_id>/withdraw/', views.withdraw_bid, name='withdraw_bid'),
    path('bid/<int:bid_id>/edit/', views.edit_bid, name='edit_bid'),
    path('bid/<int:bid_id>/counter/', views.counter_bid, name='counter_bid'),
    path('bid/<int:bid_id>/counter/respond/', views.respond_counter_bid, name='respond_counter_bid'),
    path('artisan/bids/', views.artisan_bids, name='artisan_bids'),
    path('job/artisan_bid/<int:bid_id>/', views.artisan_bid_detail, name='artisan_bid_detail'),
    path('categories/', views.category_list, name='category_list'),
    path('category/<slug:category_slug>/', views.category_detail, name='category_detail'),
    path('job/<int:job_id>/review/<str:review_type>/', views.submit_review, name='submit_review'),
    path('reviews/', views.review_list, name='review_list'),
    path('reviews/user/<int:user_id>/', views.review_list, name='user_reviews'),
    path('testimonials/', views.testimonial_list, name='testimonial_list'),
]
