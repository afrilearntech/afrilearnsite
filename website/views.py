from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone

from .forms import SurveyResponseForm, WebinarRegistrationForm
from .models import ContactMessage, NewsletterSubscriber, Survey, Webinar

class HomeView(View):
    template = 'website/index.html'
    def get(self, request):
        popup_webinar = (
            Webinar.objects.filter(
                is_published=True,
                popup_enabled=True,
                starts_at__gte=timezone.now(),
            )
            .prefetch_related("speakers")
            .order_by("starts_at")
            .first()
        )
        return render(request, self.template, {"popup_webinar": popup_webinar})


class WebinarListView(View):
    template = "website/webinars.html"

    def get(self, request):
        now = timezone.now()
        webinars = Webinar.objects.filter(is_published=True).prefetch_related("speakers")
        return render(
            request,
            self.template,
            {
                "upcoming_webinars": webinars.filter(starts_at__gte=now).order_by("starts_at"),
                "past_webinars": webinars.filter(starts_at__lt=now).order_by("-starts_at"),
            },
        )


class WebinarDetailView(View):
    template = "website/webinar_detail.html"

    def get(self, request, slug):
        webinar = get_object_or_404(
            Webinar.objects.prefetch_related("speakers", "surveys__questions"),
            slug=slug,
            is_published=True,
        )
        open_surveys = [survey for survey in webinar.surveys.all() if survey.is_open]
        return render(request, self.template, {"webinar": webinar, "open_surveys": open_surveys})


class WebinarRegistrationView(View):
    template = "website/webinar_registration.html"

    def dispatch(self, request, slug):
        self.webinar = get_object_or_404(Webinar, slug=slug, is_published=True)
        if not self.webinar.is_registration_open:
            messages.warning(request, "Registration for this webinar is closed.")
            return redirect(self.webinar.get_absolute_url())
        return super().dispatch(request, slug)

    def get(self, request, slug):
        return render(
            request,
            self.template,
            {"webinar": self.webinar, "form": WebinarRegistrationForm(webinar=self.webinar)},
        )

    def post(self, request, slug):
        form = WebinarRegistrationForm(request.POST, webinar=self.webinar)
        if form.is_valid():
            registration = form.save()
            request.session[f"webinar_registration_{self.webinar.pk}"] = registration.pk
            messages.success(request, "You’re registered. We look forward to seeing you at the webinar!")
            return redirect("website:webinar_registration_success", slug=self.webinar.slug)
        return render(request, self.template, {"webinar": self.webinar, "form": form})


def webinar_registration_success(request, slug):
    webinar = get_object_or_404(Webinar, slug=slug, is_published=True)
    return render(request, "website/webinar_registration_success.html", {"webinar": webinar})


class SurveyView(View):
    template = "website/survey.html"

    def dispatch(self, request, pk):
        self.survey = get_object_or_404(
            Survey.objects.select_related("webinar").prefetch_related("questions"),
            pk=pk,
            webinar__is_published=True,
        )
        if not self.survey.is_open:
            raise Http404("This survey is not open.")
        return super().dispatch(request, pk)

    def get(self, request, pk):
        return render(
            request,
            self.template,
            {"survey": self.survey, "form": SurveyResponseForm(survey=self.survey)},
        )

    def post(self, request, pk):
        form = SurveyResponseForm(request.POST, survey=self.survey)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you. Your survey response has been recorded.")
            return redirect(self.survey.webinar.get_absolute_url())
        return render(request, self.template, {"survey": self.survey, "form": form})


@require_POST
def contact_submit(request):
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()

    if not (name and email and subject and message):
        messages.error(request, 'Please fill in all required fields.')
        return redirect('website:home')

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
