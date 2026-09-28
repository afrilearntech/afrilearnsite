import csv
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.text import slugify


class AfriLearnAdminConfig(AdminConfig):
    default_site = "afrilearnsite.admin.AfriLearnAdminSite"


class AfriLearnAdminSite(AdminSite):
    site_header = "AfriLearnTech Administration"
    site_title = "AfriLearnTech Admin"
    index_title = "Dashboard"
    index_template = "admin/dashboard.html"

    def each_context(self, request):
        context = super().each_context(request)
        reporting_url = reverse("admin:reporting")
        notifications_url = reverse("admin:webinar_notifications")
        if request.path.startswith(notifications_url):
            active_tab = "notifications"
        elif request.path.startswith(reporting_url):
            active_tab = "reporting"
        elif request.path == reverse("admin:index"):
            active_tab = "dashboard"
        else:
            active_tab = ""
        context["active_admin_tab"] = active_tab
        return context

    def get_urls(self):
        custom_urls = [
            path(
                "notifications/",
                self.admin_view(self.webinar_notifications_view),
                name="webinar_notifications",
            ),
            path(
                "webinars/<int:webinar_id>/registrations.csv",
                self.admin_view(self.export_webinar_registrations),
                name="webinar_export_registrations",
            ),
            path("reporting/", self.admin_view(self.reporting_view), name="reporting"),
            path(
                "reporting/export/registrations/",
                self.admin_view(self.export_registrations),
                name="reporting_export_registrations",
            ),
            path(
                "reporting/export/visits/",
                self.admin_view(self.export_visits),
                name="reporting_export_visits",
            ),
        ]
        return custom_urls + super().get_urls()

    @staticmethod
    def _csv_safe(value):
        """Prevent user-controlled values from becoming spreadsheet formulas."""
        if value is None:
            return ""
        text = str(value)
        if text.startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{text}"
        return text

    def _registration_export(self, queryset, filename):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(
            [
                "Webinar",
                "First name",
                "Last name",
                "Email",
                "Phone",
                "Organization",
                "Job title",
                "Expectations",
                "Status",
                "Consent to updates",
                "Registered at",
            ]
        )
        for registration in queryset.select_related("webinar").order_by("-registered_at"):
            writer.writerow(
                [
                    self._csv_safe(registration.webinar.title),
                    self._csv_safe(registration.first_name),
                    self._csv_safe(registration.last_name),
                    self._csv_safe(registration.email),
                    self._csv_safe(registration.phone),
                    self._csv_safe(registration.organization),
                    self._csv_safe(registration.job_title),
                    self._csv_safe(registration.expectations),
                    registration.get_status_display(),
                    "Yes" if registration.consent_to_updates else "No",
                    registration.registered_at.isoformat(),
                ]
            )
        return response

    def export_webinar_registrations(self, request, webinar_id):
        from website.models import Webinar

        if not request.user.has_perm("website.view_webinarregistration"):
            raise PermissionDenied
        webinar = get_object_or_404(Webinar, pk=webinar_id)
        filename = f"{slugify(webinar.title) or 'webinar'}-registrations.csv"
        return self._registration_export(webinar.registrations.all(), filename)

    def webinar_notifications_view(self, request):
        from website.forms_admin import WebinarNotificationForm
        from website.models import Webinar, WebinarNotification
        from website.webinar_notifications import (
            NoNotificationRecipients,
            audience_counts,
            send_webinar_notification,
        )

        if not request.user.has_perm("website.add_webinarnotification"):
            raise PermissionDenied

        selected_id = request.POST.get("webinar") or request.GET.get("webinar")
        selected_webinar = (
            Webinar.objects.filter(pk=int(selected_id)).first()
            if selected_id and str(selected_id).isdigit()
            else None
        )
        initial = {"webinar": selected_webinar, "audience": WebinarNotification.Audience.ACTIVE}
        if selected_webinar:
            initial["subject"] = f"Important information: {selected_webinar.title}"

        if request.method == "POST":
            form = WebinarNotificationForm(request.POST)
            if form.is_valid():
                if not settings.WEBINAR_EMAIL_NOTIFICATIONS_ENABLED:
                    form.add_error(
                        None,
                        "Outbound webinar email is disabled until the production SMTP settings are configured.",
                    )
                else:
                    try:
                        notification = send_webinar_notification(
                            webinar=form.cleaned_data["webinar"],
                            audience=form.cleaned_data["audience"],
                            subject=form.cleaned_data["subject"],
                            message=form.cleaned_data["message"],
                            user=request.user,
                        )
                    except NoNotificationRecipients as exc:
                        form.add_error("audience", str(exc))
                    else:
                        if notification.failed_count == 0:
                            messages.success(
                                request,
                                f"Notification sent to {notification.delivered_count} participant(s).",
                            )
                        elif notification.delivered_count:
                            messages.warning(
                                request,
                                f"Sent {notification.delivered_count} email(s); "
                                f"{notification.failed_count} failed. Open the delivery log for details.",
                            )
                        else:
                            messages.error(
                                request,
                                "No emails were delivered. Open the delivery log and check the outbound email settings.",
                            )
                        return redirect(
                            f"{reverse('admin:webinar_notifications')}?webinar={notification.webinar_id}"
                        )
        else:
            form = WebinarNotificationForm(initial=initial)

        form_webinar_id = form["webinar"].value()
        if not selected_webinar and form_webinar_id and str(form_webinar_id).isdigit():
            selected_webinar = Webinar.objects.filter(pk=int(form_webinar_id)).first()
        counts = audience_counts(selected_webinar) if selected_webinar else {}
        audience_rows = [
            {"value": value, "label": label, "count": counts.get(value, 0)}
            for value, label in WebinarNotification.Audience.choices
        ]
        notifications = WebinarNotification.objects.select_related("webinar", "created_by")
        if selected_webinar:
            notifications = notifications.filter(webinar=selected_webinar)

        context = {
            **self.each_context(request),
            "title": "Participant notifications",
            "form": form,
            "selected_webinar": selected_webinar,
            "audience_rows": audience_rows,
            "notifications": notifications[:30],
            "email_sender": settings.DEFAULT_FROM_EMAIL,
            "email_enabled": settings.WEBINAR_EMAIL_NOTIFICATIONS_ENABLED,
        }
        return TemplateResponse(request, "admin/webinar_notifications.html", context)

    @staticmethod
    def _chart_rows(queryset, label_format):
        rows = list(queryset)
        maximum = max((row["total"] for row in rows), default=1)
        for row in rows:
            row["label"] = label_format(row["period"])
            row["percentage"] = round((row["total"] / maximum) * 100) if maximum else 0
        return rows

    def dashboard_metrics(self):
        from website.models import ContactMessage, NewsletterSubscriber, SiteVisit, Webinar, WebinarRegistration

        now = timezone.now()
        return {
            "visits_7_days": SiteVisit.objects.filter(visited_at__gte=now - timedelta(days=7)).count(),
            "visits_30_days": SiteVisit.objects.filter(visited_at__gte=now - timedelta(days=30)).count(),
            "unique_visitors_30_days": SiteVisit.objects.filter(
                visited_at__gte=now - timedelta(days=30)
            ).exclude(session_key="").values("session_key").distinct().count(),
            "upcoming_webinars": Webinar.objects.filter(is_published=True, starts_at__gte=now).count(),
            "registrations": WebinarRegistration.objects.exclude(
                status=WebinarRegistration.Status.CANCELLED
            ).count(),
            "subscribers": NewsletterSubscriber.objects.count(),
            "unread_messages": ContactMessage.objects.count(),
        }

    def index(self, request, extra_context=None):
        from website.models import SiteVisit, WebinarRegistration

        now = timezone.now()
        daily = (
            SiteVisit.objects.filter(visited_at__gte=now - timedelta(days=6))
            .annotate(period=TruncDate("visited_at"))
            .values("period")
            .annotate(total=Count("id"))
            .order_by("period")
        )
        context = {
            "metrics": self.dashboard_metrics(),
            "daily_visits": self._chart_rows(daily, lambda value: value.strftime("%a %d")),
            "recent_registrations": WebinarRegistration.objects.select_related("webinar")[:8],
        }
        if extra_context:
            context.update(extra_context)
        return super().index(request, context)

    def reporting_view(self, request):
        from website.models import SiteVisit, Survey, Webinar, WebinarRegistration

        now = timezone.now()
        daily = (
            SiteVisit.objects.filter(visited_at__gte=now - timedelta(days=29))
            .annotate(period=TruncDate("visited_at"))
            .values("period")
            .annotate(total=Count("id"))
            .order_by("period")
        )
        weekly = (
            SiteVisit.objects.filter(visited_at__gte=now - timedelta(weeks=11))
            .annotate(period=TruncWeek("visited_at"))
            .values("period")
            .annotate(total=Count("id"))
            .order_by("period")
        )
        monthly = (
            SiteVisit.objects.filter(visited_at__gte=now - timedelta(days=365))
            .annotate(period=TruncMonth("visited_at"))
            .values("period")
            .annotate(total=Count("id"))
            .order_by("period")
        )
        webinar_rows = Webinar.objects.annotate(
            registration_total=Count(
                "registrations",
                filter=~Q(registrations__status=WebinarRegistration.Status.CANCELLED),
                distinct=True,
            ),
            attended_total=Count(
                "registrations",
                filter=Q(registrations__status=WebinarRegistration.Status.ATTENDED),
                distinct=True,
            ),
            survey_response_total=Count("surveys__responses", distinct=True),
        ).order_by("-starts_at")
        survey_rows = Survey.objects.select_related("webinar").annotate(
            response_total=Count("responses")
        ).order_by("-created_at")
        top_pages = list(
            SiteVisit.objects.values("path").annotate(total=Count("id")).order_by("-total", "path")[:12]
        )

        context = {
            **self.each_context(request),
            "title": "Reporting",
            "metrics": self.dashboard_metrics(),
            "daily_visits": self._chart_rows(daily, lambda value: value.strftime("%d %b")),
            "weekly_visits": self._chart_rows(weekly, lambda value: f"Week of {value:%d %b}"),
            "monthly_visits": self._chart_rows(monthly, lambda value: value.strftime("%b %Y")),
            "webinar_rows": webinar_rows,
            "survey_rows": survey_rows,
            "top_pages": top_pages,
        }
        return TemplateResponse(request, "admin/reporting.html", context)

    def export_registrations(self, request):
        from website.models import WebinarRegistration

        if not request.user.has_perm("website.view_webinarregistration"):
            raise PermissionDenied
        return self._registration_export(
            WebinarRegistration.objects.all(),
            "webinar-registrations.csv",
        )

    def export_visits(self, request):
        from website.models import SiteVisit

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="site-visits.csv"'
        writer = csv.writer(response)
        writer.writerow(["Path", "Session", "Referrer", "Visited at"])
        for visit in SiteVisit.objects.order_by("-visited_at"):
            writer.writerow([visit.path, visit.session_key, visit.referrer, visit.visited_at.isoformat()])
        return response
