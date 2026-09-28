from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.utils import timezone

from .models import (
    WebinarNotification,
    WebinarNotificationRecipient,
    WebinarRegistration,
)


class NoNotificationRecipients(ValueError):
    pass


def registrations_for_audience(webinar, audience):
    registrations = webinar.registrations.order_by("email")
    if audience == WebinarNotification.Audience.ACTIVE:
        return registrations.exclude(status=WebinarRegistration.Status.CANCELLED)
    return registrations.filter(status=audience)


def audience_counts(webinar):
    registrations = webinar.registrations.all()
    return {
        WebinarNotification.Audience.ACTIVE: registrations.exclude(
            status=WebinarRegistration.Status.CANCELLED
        ).count(),
        WebinarNotification.Audience.REGISTERED: registrations.filter(
            status=WebinarRegistration.Status.REGISTERED
        ).count(),
        WebinarNotification.Audience.ATTENDED: registrations.filter(
            status=WebinarRegistration.Status.ATTENDED
        ).count(),
        WebinarNotification.Audience.NO_SHOW: registrations.filter(
            status=WebinarRegistration.Status.NO_SHOW
        ).count(),
        WebinarNotification.Audience.CANCELLED: registrations.filter(
            status=WebinarRegistration.Status.CANCELLED
        ).count(),
    }


def _email_body(notification, recipient):
    start = timezone.localtime(notification.webinar.starts_at)
    return (
        f"Hello {recipient.name or 'there'},\n\n"
        f"{notification.message}\n\n"
        f"Webinar: {notification.webinar.title}\n"
        f"Date and time: {start:%A, %d %B %Y at %H:%M %Z}\n\n"
        "Regards,\nAfriLearnTech"
    )


def send_webinar_notification(*, webinar, audience, subject, message, user):
    registrations = list(registrations_for_audience(webinar, audience))
    if not registrations:
        raise NoNotificationRecipients("There are no registrations in the selected audience.")

    with transaction.atomic():
        notification = WebinarNotification.objects.create(
            webinar=webinar,
            audience=audience,
            subject=subject,
            message=message,
            created_by=user,
            recipient_count=len(registrations),
        )
        WebinarNotificationRecipient.objects.bulk_create(
            [
                WebinarNotificationRecipient(
                    notification=notification,
                    registration=registration,
                    name=registration.full_name,
                    email=registration.email,
                )
                for registration in registrations
            ]
        )

    delivered = 0
    failed = 0
    connection = get_connection(fail_silently=False)
    recipients = list(notification.recipients.all())

    try:
        connection.open()
        for recipient in recipients:
            try:
                email = EmailMultiAlternatives(
                    subject=notification.subject,
                    body=_email_body(notification, recipient),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient.email],
                    connection=connection,
                )
                sent = email.send(fail_silently=False)
                if sent != 1:
                    raise RuntimeError("The email backend did not confirm delivery.")
            except Exception as exc:
                failed += 1
                WebinarNotificationRecipient.objects.filter(pk=recipient.pk).update(
                    status=WebinarNotificationRecipient.Status.FAILED,
                    error_message=str(exc)[:1000],
                )
            else:
                delivered += 1
                WebinarNotificationRecipient.objects.filter(pk=recipient.pk).update(
                    status=WebinarNotificationRecipient.Status.SENT,
                    error_message="",
                    sent_at=timezone.now(),
                )
    except Exception as exc:
        error_message = str(exc)[:1000]
        pending_ids = [recipient.pk for recipient in recipients]
        WebinarNotificationRecipient.objects.filter(pk__in=pending_ids).update(
            status=WebinarNotificationRecipient.Status.FAILED,
            error_message=error_message,
        )
        delivered = 0
        failed = len(recipients)
    finally:
        try:
            connection.close()
        except Exception:
            # Delivery outcomes are already recorded above; a connection-close
            # failure must not prevent the campaign totals from being finalized.
            pass

    if failed == 0:
        status = WebinarNotification.Status.SENT
    elif delivered:
        status = WebinarNotification.Status.PARTIAL
    else:
        status = WebinarNotification.Status.FAILED

    WebinarNotification.objects.filter(pk=notification.pk).update(
        status=status,
        delivered_count=delivered,
        failed_count=failed,
        completed_at=timezone.now(),
    )
    notification.refresh_from_db()
    return notification
