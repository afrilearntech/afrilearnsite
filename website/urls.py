from django.urls import path
from .views import (
    HomeView,
    SurveyView,
    WebinarDetailView,
    WebinarListView,
    WebinarRegistrationView,
    contact_submit,
    newsletter_subscribe,
    webinar_registration_success,
)

app_name = 'website'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('webinars/', WebinarListView.as_view(), name='webinars'),
    path('webinars/<slug:slug>/', WebinarDetailView.as_view(), name='webinar_detail'),
    path('webinars/<slug:slug>/register/', WebinarRegistrationView.as_view(), name='webinar_register'),
    path('webinars/<slug:slug>/registered/', webinar_registration_success, name='webinar_registration_success'),
    path('surveys/<int:pk>/', SurveyView.as_view(), name='survey'),
    path('contact/', contact_submit, name='contact'),
    path('newsletter/', newsletter_subscribe, name='newsletter'),
]
