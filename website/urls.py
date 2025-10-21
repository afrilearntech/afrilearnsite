from django.urls import path
from .views import HomeView, contact_submit, newsletter_subscribe

app_name = 'website'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('contact/', contact_submit, name='contact'),
    path('newsletter/', newsletter_subscribe, name='newsletter'),
]