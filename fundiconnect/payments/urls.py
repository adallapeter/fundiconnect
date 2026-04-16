from django.urls import path
from . import views

urlpatterns = [
    path('pay/', views.payments, name='payments'),
]
