import csv
from datetime import timedelta

from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone


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
        if request.path.startswith(reporting_url):
            active_tab = "reporting"
        elif request.path == reverse("admin:index"):
            active_tab = "dashboard"
        else:
            active_tab = ""
        context["active_admin_tab"] = active_tab
        return context

    def get_urls(self):
        custom_urls = [
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

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="webinar-registrations.csv"'
        writer = csv.writer(response)
        writer.writerow(
            ["Webinar", "First name", "Last name", "Email", "Phone", "Organization", "Job title", "Status", "Registered at"]
        )
        for registration in WebinarRegistration.objects.select_related("webinar").order_by("-registered_at"):
            writer.writerow(
                [
                    registration.webinar.title,
                    registration.first_name,
                    registration.last_name,
                    registration.email,
                    registration.phone,
                    registration.organization,
                    registration.job_title,
                    registration.get_status_display(),
                    registration.registered_at.isoformat(),
                ]
            )
        return response

    def export_visits(self, request):
        from website.models import SiteVisit

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="site-visits.csv"'
        writer = csv.writer(response)
        writer.writerow(["Path", "Session", "Referrer", "Visited at"])
        for visit in SiteVisit.objects.order_by("-visited_at"):
            writer.writerow([visit.path, visit.session_key, visit.referrer, visit.visited_at.isoformat()])
        return response
