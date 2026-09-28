import csv
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    SiteVisit,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
    SurveyResponse,
    Webinar,
    WebinarNotification,
    WebinarNotificationRecipient,
    WebinarRegistration,
)


class WebinarModelTests(TestCase):
    def test_slug_and_registration_state_are_derived(self):
        webinar = Webinar.objects.create(
            title="Future of Digital Learning",
            description="A practical session.",
            starts_at=timezone.now() + timedelta(days=2),
        )
        self.assertEqual(webinar.slug, "future-of-digital-learning")
        self.assertTrue(webinar.is_upcoming)
        self.assertTrue(webinar.is_registration_open)

    def test_capacity_closes_registration(self):
        webinar = Webinar.objects.create(
            title="Capacity Test",
            description="Testing limits.",
            starts_at=timezone.now() + timedelta(days=2),
            capacity=1,
        )
        WebinarRegistration.objects.create(
            webinar=webinar,
            first_name="Ada",
            last_name="Mensah",
            email="ada@example.com",
        )
        self.assertFalse(webinar.is_registration_open)


class WebinarPublicFlowTests(TestCase):
    def setUp(self):
        self.upcoming = Webinar.objects.create(
            title="AI for African Classrooms",
            description="A webinar about practical classroom innovation.",
            starts_at=timezone.now() + timedelta(days=5),
            popup_enabled=True,
        )
        self.past = Webinar.objects.create(
            title="Past Education Forum",
            description="A previous conversation.",
            starts_at=timezone.now() - timedelta(days=5),
        )

    def test_webinar_list_separates_upcoming_and_past(self):
        response = self.client.get(reverse("website:webinars"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.upcoming.title)
        self.assertContains(response, self.past.title)
        self.assertEqual(list(response.context["upcoming_webinars"]), [self.upcoming])
        self.assertEqual(list(response.context["past_webinars"]), [self.past])

    def test_registration_flow_creates_one_registration_per_email(self):
        url = reverse("website:webinar_register", args=[self.upcoming.slug])
        data = {
            "first_name": "Ama",
            "last_name": "Boateng",
            "email": "AMA@example.com",
            "phone": "+233000000000",
            "organization": "AfriLearn School",
            "job_title": "Teacher",
            "expectations": "New ideas",
        }
        response = self.client.post(url, data)
        self.assertRedirects(
            response,
            reverse("website:webinar_registration_success", args=[self.upcoming.slug]),
        )
        self.assertEqual(WebinarRegistration.objects.count(), 1)
        self.assertEqual(WebinarRegistration.objects.get().email, "ama@example.com")

        duplicate = self.client.post(url, {**data, "email": "ama@EXAMPLE.com"})
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, "already registered")
        self.assertEqual(WebinarRegistration.objects.count(), 1)

    def test_active_popup_and_gallery_links_render_correctly(self):
        response = self.client.get(reverse("website:home"))
        self.assertContains(response, "webinarPromoModal")
        self.assertContains(response, self.upcoming.title)
        self.assertContains(response, "const popupChance = 0.70")
        self.assertContains(response, "const cooldownMs = 15 * 60 * 1000")
        self.assertContains(response, "const showDelayMs = 2000")
        self.assertContains(response, "shown.bs.modal")
        self.assertNotContains(response, "{\\% static")
        self.assertContains(response, "/static/img/gallery/g8.png")

    def test_public_html_visit_is_recorded(self):
        SiteVisit.objects.all().delete()
        self.client.get(reverse("website:webinars"))
        visit = SiteVisit.objects.get()
        self.assertEqual(visit.path, "/webinars/")
        self.assertTrue(visit.session_key)


class SurveyFlowTests(TestCase):
    def setUp(self):
        self.webinar = Webinar.objects.create(
            title="Survey Webinar",
            description="Feedback test.",
            starts_at=timezone.now() + timedelta(days=3),
        )
        self.registration = WebinarRegistration.objects.create(
            webinar=self.webinar,
            first_name="Kojo",
            last_name="Asare",
            email="kojo@example.com",
        )
        self.survey = Survey.objects.create(
            webinar=self.webinar,
            kind=Survey.Kind.PRE,
            title="Before we meet",
            requires_registration=True,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            prompt="What would you like to learn?",
            question_type=SurveyQuestion.QuestionType.LONG_TEXT,
        )

    def test_registered_attendee_can_submit_survey(self):
        response = self.client.post(
            reverse("website:survey", args=[self.survey.pk]),
            {
                "name": "Kojo Asare",
                "email": "KOJO@example.com",
                f"question_{self.question.pk}": "How to use AI responsibly.",
            },
        )
        self.assertRedirects(response, self.webinar.get_absolute_url())
        survey_response = SurveyResponse.objects.get()
        self.assertEqual(survey_response.registration, self.registration)
        self.assertEqual(SurveyAnswer.objects.get().value, "How to use AI responsibly.")

    def test_unregistered_email_is_rejected_when_required(self):
        response = self.client.post(
            reverse("website:survey", args=[self.survey.pk]),
            {
                "name": "Visitor",
                "email": "visitor@example.com",
                f"question_{self.question.pk}": "Learning",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "registered for this webinar")
        self.assertFalse(SurveyResponse.objects.exists())


class AdminAnalyticsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="secret-test-password",
        )
        self.client.force_login(self.user)

    def test_dashboard_and_reporting_tabs_load(self):
        dashboard = self.client.get(reverse("admin:index"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Dashboard")
        self.assertContains(dashboard, "Reporting")
        self.assertContains(dashboard, "Visits · 30 days")

        reporting = self.client.get(reverse("admin:reporting"))
        self.assertEqual(reporting.status_code, 200)
        self.assertContains(reporting, "Webinar registrations and engagement")
        self.assertContains(reporting, "Export registrations")

    def test_csv_exports_are_available(self):
        response = self.client.get(reverse("admin:reporting_export_registrations"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="AfriLearnTech <notifications@example.com>",
    WEBINAR_EMAIL_NOTIFICATIONS_ENABLED=True,
)
class AdminParticipantToolsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="participant-admin",
            email="admin@example.com",
            password="secret-test-password",
        )
        self.client.force_login(self.user)
        self.webinar = Webinar.objects.create(
            title="Participant Tools Webinar",
            description="Admin tools test.",
            starts_at=timezone.now() + timedelta(days=3),
        )
        self.active_registration = WebinarRegistration.objects.create(
            webinar=self.webinar,
            first_name="Ama",
            last_name="Boateng",
            email="ama@example.com",
            organization="=UNSAFE()",
            expectations="Practical guidance",
        )
        self.cancelled_registration = WebinarRegistration.objects.create(
            webinar=self.webinar,
            first_name="Kojo",
            last_name="Asare",
            email="kojo@example.com",
            status=WebinarRegistration.Status.CANCELLED,
        )
        other_webinar = Webinar.objects.create(
            title="Other Webinar",
            description="Out of scope.",
            starts_at=timezone.now() + timedelta(days=4),
        )
        WebinarRegistration.objects.create(
            webinar=other_webinar,
            first_name="Else",
            last_name="Where",
            email="elsewhere@example.com",
        )

    def test_per_webinar_export_contains_all_and_only_its_registrations(self):
        response = self.client.get(
            reverse("admin:webinar_export_registrations", args=[self.webinar.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 3)
        csv_text = response.content.decode("utf-8-sig")
        self.assertIn("ama@example.com", csv_text)
        self.assertIn("kojo@example.com", csv_text)
        self.assertNotIn("elsewhere@example.com", csv_text)
        self.assertIn("'=UNSAFE()", csv_text)

    def test_notification_center_sends_privately_and_records_delivery_log(self):
        response = self.client.post(
            reverse("admin:webinar_notifications"),
            {
                "webinar": self.webinar.pk,
                "audience": WebinarNotification.Audience.ACTIVE,
                "subject": "Your webinar reminder",
                "message": "We look forward to seeing you.",
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('admin:webinar_notifications')}?webinar={self.webinar.pk}",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ama@example.com"])
        self.assertNotIn("kojo@example.com", mail.outbox[0].to)
        self.assertIn("Participant Tools Webinar", mail.outbox[0].body)

        notification = WebinarNotification.objects.get()
        self.assertEqual(notification.status, WebinarNotification.Status.SENT)
        self.assertEqual(notification.recipient_count, 1)
        self.assertEqual(notification.delivered_count, 1)
        self.assertEqual(notification.failed_count, 0)
        recipient = WebinarNotificationRecipient.objects.get()
        self.assertEqual(recipient.registration, self.active_registration)
        self.assertEqual(recipient.status, WebinarNotificationRecipient.Status.SENT)
        self.assertIsNotNone(recipient.sent_at)

    def test_notification_center_shows_audience_and_delivery_log(self):
        response = self.client.get(
            f"{reverse('admin:webinar_notifications')}?webinar={self.webinar.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Participant notifications")
        self.assertContains(response, self.webinar.title)
        self.assertContains(response, "All active registrations")
        self.assertContains(response, "Download registrations")

    @override_settings(WEBINAR_EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_notification_sending_is_blocked_until_smtp_is_enabled(self):
        response = self.client.post(
            reverse("admin:webinar_notifications"),
            {
                "webinar": self.webinar.pk,
                "audience": WebinarNotification.Audience.ACTIVE,
                "subject": "Must not send",
                "message": "SMTP has not been enabled.",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Outbound webinar email is disabled")
        self.assertFalse(WebinarNotification.objects.exists())
        self.assertEqual(len(mail.outbox), 0)


class SeedDataCommandTests(TestCase):
    def test_seed_command_is_idempotent(self):
        output = StringIO()
        call_command("seed_demo_data", "--skip-visits", stdout=output)
        first_counts = (
            Webinar.objects.count(),
            WebinarRegistration.objects.count(),
            Survey.objects.count(),
            SurveyResponse.objects.count(),
        )

        call_command("seed_demo_data", "--skip-visits", stdout=output)
        second_counts = (
            Webinar.objects.count(),
            WebinarRegistration.objects.count(),
            Survey.objects.count(),
            SurveyResponse.objects.count(),
        )

        self.assertEqual(first_counts, (5, 119, 2, 20))
        self.assertEqual(second_counts, first_counts)
