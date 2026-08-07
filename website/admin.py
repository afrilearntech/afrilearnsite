from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ContactMessage,
    NewsletterSubscriber,
    SiteVisit,
    Speaker,
    Survey,
    SurveyAnswer,
    SurveyQuestion,
    SurveyResponse,
    Webinar,
    WebinarRegistration,
)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "created_at")
    search_fields = ("name", "email", "subject", "message")
    list_filter = ("created_at",)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "subscribed_at")
    search_fields = ("email",)
    list_filter = ("subscribed_at",)


@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "organization")
    search_fields = ("name", "role", "organization", "bio")


@admin.register(Webinar)
class WebinarAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "starts_at",
        "is_published",
        "popup_enabled",
        "registration_total",
        "registration_state",
    )
    list_filter = ("is_published", "popup_enabled", "starts_at")
    search_fields = ("title", "description", "speakers__name")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("speakers",)
    readonly_fields = ("flyer_preview", "created_at", "updated_at")
    date_hierarchy = "starts_at"
    fieldsets = (
        ("Webinar", {"fields": ("title", "slug", "description", "flyer", "flyer_preview", "speakers")}),
        ("Schedule", {"fields": ("starts_at", "ends_at", "registration_deadline", "capacity")}),
        ("Links", {"fields": ("meeting_url", "recording_url")}),
        ("Publishing", {"fields": ("is_published", "popup_enabled", "created_at", "updated_at")}),
    )

    @admin.display(description="Flyer")
    def flyer_preview(self, obj):
        if obj and obj.flyer:
            return format_html('<img src="{}" alt="" style="max-width:360px;max-height:220px;border-radius:10px">', obj.flyer.url)
        return "No flyer uploaded"

    @admin.display(description="Registrations")
    def registration_total(self, obj):
        return obj.registration_count

    @admin.display(description="Registration")
    def registration_state(self, obj):
        return "Open" if obj.is_registration_open else "Closed"


@admin.action(description="Mark selected registrations as attended")
def mark_attended(modeladmin, request, queryset):
    queryset.update(status=WebinarRegistration.Status.ATTENDED)


@admin.register(WebinarRegistration)
class WebinarRegistrationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "webinar", "status", "organization", "registered_at")
    list_filter = ("status", "webinar", "registered_at", "consent_to_updates")
    search_fields = ("first_name", "last_name", "email", "organization", "webinar__title")
    readonly_fields = ("registered_at",)
    autocomplete_fields = ("webinar",)
    date_hierarchy = "registered_at"
    actions = (mark_attended,)


class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 1
    fields = ("order", "prompt", "question_type", "choices", "is_required")


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("title", "webinar", "kind", "is_active", "open_state", "response_total")
    list_filter = ("kind", "is_active", "webinar")
    search_fields = ("title", "webinar__title", "introduction")
    autocomplete_fields = ("webinar",)
    inlines = (SurveyQuestionInline,)

    @admin.display(description="Status")
    def open_state(self, obj):
        return "Open" if obj.is_open else "Closed"

    @admin.display(description="Responses")
    def response_total(self, obj):
        return obj.responses.count()


class SurveyAnswerInline(admin.TabularInline):
    model = SurveyAnswer
    extra = 0
    can_delete = False
    readonly_fields = ("question", "value")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "survey", "submitted_at")
    list_filter = ("survey__kind", "survey__webinar", "submitted_at")
    search_fields = ("name", "email", "survey__title", "survey__webinar__title")
    readonly_fields = ("survey", "registration", "name", "email", "submitted_at")
    inlines = (SurveyAnswerInline,)

    def has_add_permission(self, request):
        return False


@admin.register(SiteVisit)
class SiteVisitAdmin(admin.ModelAdmin):
    list_display = ("path", "session_key", "visited_at")
    list_filter = ("visited_at", "path")
    search_fields = ("path", "session_key", "referrer")
    readonly_fields = ("path", "session_key", "referrer", "user_agent", "visited_at")
    date_hierarchy = "visited_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
from django.contrib import admin

# Register your models here.
