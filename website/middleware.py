from .models import SiteVisit


class VisitTrackingMiddleware:
    """Record successful public HTML page views for lightweight site analytics."""

    ignored_prefixes = ("/admin/", "/static/", "/assets/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get("Content-Type", "")
        if (
            request.method == "GET"
            and response.status_code < 400
            and "text/html" in content_type
            and not request.path.startswith(self.ignored_prefixes)
        ):
            try:
                if not request.session.session_key:
                    request.session.create()
                SiteVisit.objects.create(
                    path=request.path[:500],
                    session_key=(request.session.session_key or "")[:40],
                    referrer=request.META.get("HTTP_REFERER", "")[:500],
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                )
            except Exception:
                pass
        return response
