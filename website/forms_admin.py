from django import forms

from .models import Webinar, WebinarNotification


class WebinarNotificationForm(forms.Form):
    webinar = forms.ModelChoiceField(
        queryset=Webinar.objects.none(),
        empty_label="Choose a webinar",
    )
    audience = forms.ChoiceField(
        choices=WebinarNotification.Audience.choices,
        initial=WebinarNotification.Audience.ACTIVE,
        help_text="Active registrations excludes cancelled registrations.",
    )
    subject = forms.CharField(max_length=240)
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 10}),
        help_text="Each recipient receives a private, individually addressed email.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["webinar"].queryset = Webinar.objects.order_by("-starts_at", "title")

    def clean_subject(self):
        subject = self.cleaned_data["subject"].strip()
        if "\r" in subject or "\n" in subject:
            raise forms.ValidationError("The subject must be a single line.")
        return subject

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if not message:
            raise forms.ValidationError("Enter a message for the participants.")
        return message
