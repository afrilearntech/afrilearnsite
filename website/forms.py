from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import SurveyAnswer, SurveyQuestion, SurveyResponse, WebinarRegistration


class WebinarRegistrationForm(forms.ModelForm):
    consent_to_updates = forms.BooleanField(
        required=False,
        label="Send me occasional updates about AfriLearnTech events",
    )

    class Meta:
        model = WebinarRegistration
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone",
            "organization",
            "job_title",
            "expectations",
            "consent_to_updates",
        )
        widgets = {"expectations": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, webinar, **kwargs):
        super().__init__(*args, **kwargs)
        self.webinar = webinar
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if WebinarRegistration.objects.filter(webinar=self.webinar, email__iexact=email).exists():
            raise ValidationError("This email is already registered for the webinar.")
        return email

    def save(self, commit=True):
        registration = super().save(commit=False)
        registration.webinar = self.webinar
        if commit:
            registration.save()
        return registration


class SurveyResponseForm(forms.Form):
    name = forms.CharField(max_length=200)
    email = forms.EmailField()

    def __init__(self, *args, survey, **kwargs):
        super().__init__(*args, **kwargs)
        self.survey = survey
        self.registration = None
        self.questions = list(survey.questions.all())
        self.fields["name"].widget.attrs.update({"class": "form-control", "autocomplete": "name"})
        self.fields["email"].widget.attrs.update({"class": "form-control", "autocomplete": "email"})

        for question in self.questions:
            field_name = f"question_{question.pk}"
            common = {"label": question.prompt, "required": question.is_required}
            if question.question_type == SurveyQuestion.QuestionType.LONG_TEXT:
                field = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), **common)
            elif question.question_type == SurveyQuestion.QuestionType.SINGLE_CHOICE:
                choices = [(choice, choice) for choice in question.choice_list]
                field = forms.ChoiceField(choices=choices, widget=forms.RadioSelect, **common)
            elif question.question_type == SurveyQuestion.QuestionType.MULTIPLE_CHOICE:
                choices = [(choice, choice) for choice in question.choice_list]
                field = forms.MultipleChoiceField(choices=choices, widget=forms.CheckboxSelectMultiple, **common)
            elif question.question_type == SurveyQuestion.QuestionType.RATING:
                field = forms.ChoiceField(
                    choices=[(str(value), str(value)) for value in range(1, 6)],
                    widget=forms.RadioSelect,
                    **common,
                )
            elif question.question_type == SurveyQuestion.QuestionType.YES_NO:
                field = forms.ChoiceField(
                    choices=(("Yes", "Yes"), ("No", "No")),
                    widget=forms.RadioSelect,
                    **common,
                )
            else:
                field = forms.CharField(max_length=500, **common)

            if not isinstance(field.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                field.widget.attrs["class"] = "form-control"
            self.fields[field_name] = field

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if SurveyResponse.objects.filter(survey=self.survey, email__iexact=email).exists():
            raise ValidationError("A response has already been submitted with this email.")
        return email

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        if email and self.survey.requires_registration:
            self.registration = WebinarRegistration.objects.filter(
                webinar=self.survey.webinar,
                email__iexact=email,
            ).exclude(status=WebinarRegistration.Status.CANCELLED).first()
            if not self.registration:
                self.add_error("email", "Please use the email address registered for this webinar.")
        return cleaned

    @transaction.atomic
    def save(self):
        response = SurveyResponse.objects.create(
            survey=self.survey,
            registration=self.registration,
            name=self.cleaned_data["name"],
            email=self.cleaned_data["email"],
        )
        for question in self.questions:
            value = self.cleaned_data.get(f"question_{question.pk}", "")
            if isinstance(value, list):
                value = "\n".join(value)
            SurveyAnswer.objects.create(response=response, question=question, value=value)
        return response
