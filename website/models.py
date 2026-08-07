from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.name} <{self.email}>"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Speaker(models.Model):
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=160, blank=True)
    organization = models.CharField(max_length=160, blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to="webinars/speakers/", blank=True)
    profile_url = models.URLField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        details = " · ".join(filter(None, (self.role, self.organization)))
        return f"{self.name} ({details})" if details else self.name


class Webinar(models.Model):
    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260, unique=True, blank=True)
    flyer = models.ImageField(upload_to="webinars/flyers/", blank=True)
    description = models.TextField()
    speakers = models.ManyToManyField(Speaker, related_name="webinars", blank=True)
    starts_at = models.DateTimeField("date and time")
    ends_at = models.DateTimeField(blank=True, null=True)
    registration_deadline = models.DateTimeField(blank=True, null=True)
    capacity = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Leave empty for unlimited registrations.",
    )
    meeting_url = models.URLField(blank=True)
    recording_url = models.URLField(blank=True)
    is_published = models.BooleanField(default=True)
    popup_enabled = models.BooleanField(
        default=False,
        help_text="Occasionally promote this webinar in a modal on the public website.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("starts_at",)
        indexes = [
            models.Index(fields=("is_published", "starts_at")),
            models.Index(fields=("popup_enabled", "starts_at")),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}
        if self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "The end time must be after the start time."
        if self.registration_deadline and self.registration_deadline > self.starts_at:
            errors["registration_deadline"] = "The registration deadline cannot be after the webinar starts."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:240] or "webinar"
            candidate = base_slug
            suffix = 2
            while Webinar.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base_slug[:250 - len(str(suffix))]}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("website:webinar_detail", kwargs={"slug": self.slug})

    @property
    def is_upcoming(self):
        return self.starts_at >= timezone.now()

    @property
    def is_past(self):
        return self.starts_at < timezone.now()

    @property
    def registration_count(self):
        return self.registrations.exclude(status=WebinarRegistration.Status.CANCELLED).count()

    @property
    def is_registration_open(self):
        now = timezone.now()
        if not self.is_published or self.starts_at <= now:
            return False
        if self.registration_deadline and self.registration_deadline < now:
            return False
        if self.capacity and self.registration_count >= self.capacity:
            return False
        return True


class WebinarRegistration(models.Model):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        ATTENDED = "attended", "Attended"
        NO_SHOW = "no_show", "No show"
        CANCELLED = "cancelled", "Cancelled"

    webinar = models.ForeignKey(Webinar, on_delete=models.CASCADE, related_name="registrations")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    organization = models.CharField(max_length=180, blank=True)
    job_title = models.CharField(max_length=160, blank=True)
    expectations = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REGISTERED)
    consent_to_updates = models.BooleanField(default=False)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-registered_at",)
        constraints = [
            models.UniqueConstraint(fields=("webinar", "email"), name="unique_webinar_registration_email")
        ]
        indexes = [models.Index(fields=("webinar", "status"))]

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.webinar.title}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Survey(models.Model):
    class Kind(models.TextChoices):
        PRE = "pre", "Pre-webinar"
        POST = "post", "Post-webinar"

    webinar = models.ForeignKey(Webinar, on_delete=models.CASCADE, related_name="surveys")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    title = models.CharField(max_length=240)
    introduction = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    opens_at = models.DateTimeField(blank=True, null=True)
    closes_at = models.DateTimeField(blank=True, null=True)
    requires_registration = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("webinar", "kind", "created_at")

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"

    def clean(self):
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValidationError({"closes_at": "The close time must be after the open time."})

    @property
    def is_open(self):
        now = timezone.now()
        return (
            self.is_active
            and (not self.opens_at or self.opens_at <= now)
            and (not self.closes_at or self.closes_at >= now)
        )


class SurveyQuestion(models.Model):
    class QuestionType(models.TextChoices):
        SHORT_TEXT = "short_text", "Short text"
        LONG_TEXT = "long_text", "Long text"
        SINGLE_CHOICE = "single_choice", "Single choice"
        MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"
        RATING = "rating", "Rating (1–5)"
        YES_NO = "yes_no", "Yes / No"

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    prompt = models.CharField(max_length=500)
    question_type = models.CharField(max_length=24, choices=QuestionType.choices)
    choices = models.TextField(
        blank=True,
        help_text="For choice questions, enter one option per line.",
    )
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return self.prompt

    @property
    def choice_list(self):
        return [choice.strip() for choice in self.choices.splitlines() if choice.strip()]

    def clean(self):
        if self.question_type in {self.QuestionType.SINGLE_CHOICE, self.QuestionType.MULTIPLE_CHOICE} and not self.choice_list:
            raise ValidationError({"choices": "Add at least one option for a choice question."})


class SurveyResponse(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    registration = models.ForeignKey(
        WebinarRegistration,
        on_delete=models.SET_NULL,
        related_name="survey_responses",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=200)
    email = models.EmailField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-submitted_at",)
        constraints = [
            models.UniqueConstraint(fields=("survey", "email"), name="unique_survey_response_email")
        ]

    def __str__(self):
        return f"{self.name} — {self.survey.title}"


class SurveyAnswer(models.Model):
    response = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, related_name="answers")
    value = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("response", "question"), name="unique_response_question_answer")
        ]

    def __str__(self):
        return f"Answer to {self.question_id}"


class SiteVisit(models.Model):
    path = models.CharField(max_length=500)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    referrer = models.CharField(max_length=500, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    visited_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-visited_at",)
        indexes = [models.Index(fields=("visited_at", "path"))]

    def __str__(self):
        return f"{self.path} at {self.visited_at:%Y-%m-%d %H:%M}"
