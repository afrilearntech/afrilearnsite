from django.shortcuts import redirect, render
from django.views import View
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from .models import ContactMessage, NewsletterSubscriber

class HomeView(View):
    template = 'website/index.html'
    def get(self, request):
        return render(request, self.template)


@require_POST
def contact_submit(request):
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()

    if not (name and email and subject and message):
        messages.error(request, 'Please fill in all required fields.')
        return redirect('home')

    ContactMessage.objects.create(
        name=name,
        email=email,
        subject=subject,
        message=message,
    )
    messages.success(request, 'Your message has been sent. Thank you!')
    return redirect('website:home')


@require_POST
def newsletter_subscribe(request):
    email = request.POST.get('email', '').strip()
    if not email:
        messages.error(request, 'Please provide a valid email address.')
        return redirect('website:home')

    # Create if not exists, avoid duplicate errors
    obj, created = NewsletterSubscriber.objects.get_or_create(email=email)
    if created:
        messages.success(request, 'Your subscription request has been sent. Thank you!')
    else:
        messages.info(request, 'You\'re already subscribed with this email.')
    return redirect('website:home')