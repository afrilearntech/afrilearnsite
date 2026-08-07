from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from website.models import (
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


class Command(BaseCommand):
    help = "Create realistic, idempotent demo data for webinars and reporting."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-visits",
            action="store_true",
            help="Do not generate the 90-day site visit history.",
        )

    @staticmethod
    def scheduled_datetime(days_from_now, hour):
        return (timezone.now() + timedelta(days=days_from_now)).replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0,
        )

    def seed_speakers(self):
        speaker_data = [
            {
                "name": "Dr. Ama Nyarko",
                "role": "Director of Learning Innovation",
                "organization": "AfriLearnTech",
                "bio": "Ama works with schools and public institutions to turn emerging technology into practical, inclusive learning experiences.",
            },
            {
                "name": "Kwame Mensah",
                "role": "AI & Data Education Lead",
                "organization": "Open Learning Africa",
                "bio": "Kwame designs responsible AI programmes for teachers, education leaders and young innovators across West Africa.",
            },
            {
                "name": "Mariama Johnson",
                "role": "Digital Learning Strategist",
                "organization": "Learning Futures Lab",
                "bio": "Mariama helps organisations design accessible digital programmes that work for learners in low-connectivity environments.",
            },
            {
                "name": "Emmanuel Tetteh",
                "role": "Education Data Specialist",
                "organization": "Impact Analytics Ghana",
                "bio": "Emmanuel supports education teams to move from fragmented data to useful, ethical and actionable insight.",
            },
            {
                "name": "Nana Yaa Boateng",
                "role": "Youth Innovation Programme Manager",
                "organization": "Future Skills Network",
                "bio": "Nana Yaa builds programmes that connect young people to entrepreneurship, digital skills and meaningful work.",
            },
        ]
        speakers = {}
        for data in speaker_data:
            speaker, _ = Speaker.objects.update_or_create(name=data["name"], defaults=data)
            speakers[data["name"]] = speaker
        return speakers

    def seed_webinars(self, speakers):
        webinar_data = [
            {
                "slug": "ai-ready-classrooms",
                "title": "AI-Ready Classrooms: Practical Tools for African Educators",
                "description": (
                    "Move beyond the AI hype and explore practical ways teachers can use generative AI to plan lessons, "
                    "differentiate instruction and support student creativity. This session includes live demonstrations, "
                    "responsible-use guidance and a classroom-ready implementation checklist."
                ),
                "starts_at": self.scheduled_datetime(14, 14),
                "duration": 90,
                "registration_deadline_days": 13,
                "capacity": 250,
                "popup_enabled": True,
                "speaker_names": ["Dr. Ama Nyarko", "Kwame Mensah"],
            },
            {
                "slug": "inclusive-digital-learning",
                "title": "Designing Inclusive Digital Learning for Every Learner",
                "description": (
                    "Learn how to design digital learning experiences that remain usable across different devices, abilities, "
                    "languages and connectivity levels. We will cover accessible content, low-bandwidth delivery and inclusive facilitation."
                ),
                "starts_at": self.scheduled_datetime(35, 12),
                "duration": 75,
                "registration_deadline_days": 34,
                "capacity": 180,
                "popup_enabled": True,
                "speaker_names": ["Mariama Johnson", "Dr. Ama Nyarko"],
            },
            {
                "slug": "education-data-decisions",
                "title": "From Education Data to Better Decisions",
                "description": (
                    "A practical introduction to choosing useful indicators, building trustworthy reporting routines and turning "
                    "education data into decisions that improve learner outcomes."
                ),
                "starts_at": self.scheduled_datetime(63, 15),
                "duration": 90,
                "registration_deadline_days": 62,
                "capacity": 200,
                "popup_enabled": False,
                "speaker_names": ["Emmanuel Tetteh"],
            },
            {
                "slug": "future-skills-young-africans",
                "title": "Future Skills and Meaningful Work for Young Africans",
                "description": (
                    "This conversation brought together educators and programme leaders to examine the skills young Africans "
                    "need for a changing labour market and how institutions can build stronger pathways into meaningful work."
                ),
                "starts_at": self.scheduled_datetime(-24, 13),
                "duration": 80,
                "registration_deadline_days": -25,
                "capacity": 300,
                "popup_enabled": False,
                "speaker_names": ["Nana Yaa Boateng", "Mariama Johnson"],
            },
            {
                "slug": "responsible-ai-education-leaders",
                "title": "Responsible AI for Education Leaders",
                "description": (
                    "An executive briefing on the opportunities, risks and governance choices education leaders face when "
                    "introducing AI into their institutions."
                ),
                "starts_at": self.scheduled_datetime(-67, 14),
                "duration": 90,
                "registration_deadline_days": -68,
                "capacity": 220,
                "popup_enabled": False,
                "speaker_names": ["Kwame Mensah", "Emmanuel Tetteh"],
            },
        ]

        webinars = {}
        for data in webinar_data:
            starts_at = data["starts_at"]
            defaults = {
                "title": data["title"],
                "description": data["description"],
                "starts_at": starts_at,
                "ends_at": starts_at + timedelta(minutes=data["duration"]),
                "registration_deadline": self.scheduled_datetime(data["registration_deadline_days"], 23),
                "capacity": data["capacity"],
                "popup_enabled": data["popup_enabled"],
                "is_published": True,
            }
            webinar, _ = Webinar.objects.update_or_create(slug=data["slug"], defaults=defaults)
            webinar.speakers.set(speakers[name] for name in data["speaker_names"])
            webinars[data["slug"]] = webinar
        return webinars

    def seed_registrations(self, webinars):
        first_names = ["Abena", "Kojo", "Fatima", "Samuel", "Aisha", "Kofi", "Grace", "Ibrahim", "Akosua", "Daniel"]
        last_names = ["Asare", "Mensah", "Kamara", "Owusu", "Diallo", "Boateng", "Johnson", "Bello", "Addo", "Koroma"]
        organizations = ["Bright Future School", "Community Learning Hub", "EduBridge Africa", "Open Skills Network", "Independent"]
        counts = {
            "ai-ready-classrooms": 24,
            "inclusive-digital-learning": 17,
            "education-data-decisions": 11,
            "future-skills-young-africans": 38,
            "responsible-ai-education-leaders": 29,
        }

        for slug, total in counts.items():
            webinar = webinars[slug]
            for index in range(total):
                is_past = webinar.is_past
                if is_past and index % 7 == 0:
                    status = WebinarRegistration.Status.NO_SHOW
                elif is_past:
                    status = WebinarRegistration.Status.ATTENDED
                else:
                    status = WebinarRegistration.Status.REGISTERED
                WebinarRegistration.objects.update_or_create(
                    webinar=webinar,
                    email=f"demo.{slug}.{index + 1:02d}@example.com",
                    defaults={
                        "first_name": first_names[index % len(first_names)],
                        "last_name": last_names[(index * 3) % len(last_names)],
                        "phone": f"+233 20 555 {index + 1:04d}",
                        "organization": organizations[index % len(organizations)],
                        "job_title": "Educator" if index % 3 else "Programme Manager",
                        "expectations": "Practical ideas and resources to share with my team.",
                        "status": status,
                        "consent_to_updates": index % 4 != 0,
                    },
                )

    def seed_surveys(self, webinars):
        survey_specs = [
            {
                "webinar": webinars["ai-ready-classrooms"],
                "kind": Survey.Kind.PRE,
                "title": "AI-Ready Classrooms: Participant Check-in",
                "introduction": "Help our speakers tailor the session to your experience and priorities.",
                "questions": [
                    ("How confident are you currently using AI tools for teaching?", SurveyQuestion.QuestionType.RATING, ""),
                    ("Which topic matters most to you?", SurveyQuestion.QuestionType.SINGLE_CHOICE, "Lesson planning\nAssessment\nStudent creativity\nResponsible AI"),
                    ("What would make this webinar valuable for you?", SurveyQuestion.QuestionType.LONG_TEXT, ""),
                ],
            },
            {
                "webinar": webinars["future-skills-young-africans"],
                "kind": Survey.Kind.POST,
                "title": "Future Skills Webinar Feedback",
                "introduction": "Thank you for joining us. Your feedback will shape future sessions.",
                "questions": [
                    ("How useful was the session?", SurveyQuestion.QuestionType.RATING, ""),
                    ("Would you recommend this session to a colleague?", SurveyQuestion.QuestionType.YES_NO, ""),
                    ("What is one action you will take after this webinar?", SurveyQuestion.QuestionType.LONG_TEXT, ""),
                ],
            },
        ]

        for spec in survey_specs:
            survey, created = Survey.objects.get_or_create(
                webinar=spec["webinar"],
                kind=spec["kind"],
                title=spec["title"],
                defaults={
                    "introduction": spec["introduction"],
                    "is_active": True,
                    "requires_registration": True,
                },
            )
            if not created:
                survey.introduction = spec["introduction"]
                survey.is_active = True
                survey.requires_registration = True
                survey.save(update_fields=("introduction", "is_active", "requires_registration"))

            questions = []
            for order, (prompt, question_type, choices) in enumerate(spec["questions"], start=1):
                question, _ = SurveyQuestion.objects.update_or_create(
                    survey=survey,
                    order=order,
                    defaults={
                        "prompt": prompt,
                        "question_type": question_type,
                        "choices": choices,
                        "is_required": True,
                    },
                )
                questions.append(question)

            registrations = list(
                spec["webinar"].registrations.exclude(status=WebinarRegistration.Status.NO_SHOW)[:10]
            )
            for index, registration in enumerate(registrations):
                response, _ = SurveyResponse.objects.update_or_create(
                    survey=survey,
                    email=registration.email,
                    defaults={"name": registration.full_name, "registration": registration},
                )
                for question in questions:
                    if question.question_type == SurveyQuestion.QuestionType.RATING:
                        value = str(4 + (index % 2))
                    elif question.question_type == SurveyQuestion.QuestionType.SINGLE_CHOICE:
                        value = question.choice_list[index % len(question.choice_list)]
                    elif question.question_type == SurveyQuestion.QuestionType.YES_NO:
                        value = "Yes"
                    else:
                        value = "I want practical ideas that I can apply with my learners and colleagues."
                    SurveyAnswer.objects.update_or_create(
                        response=response,
                        question=question,
                        defaults={"value": value},
                    )

    def seed_communications(self):
        for index, email in enumerate(
            [
                "adwoa@example.com",
                "mohamed@example.com",
                "esther@example.com",
                "learning-team@example.com",
                "events@example.com",
            ]
        ):
            NewsletterSubscriber.objects.get_or_create(email=email)
            ContactMessage.objects.get_or_create(
                email=email,
                subject=f"Demo enquiry {index + 1}",
                defaults={
                    "name": email.split("@")[0].replace("-", " ").title(),
                    "message": "I would like to learn more about your upcoming programmes and partnership opportunities.",
                },
            )

    def seed_visits(self):
        SiteVisit.objects.filter(session_key__startswith="seed-").delete()
        paths = [
            "/",
            "/",
            "/webinars/",
            "/webinars/ai-ready-classrooms/",
            "/webinars/inclusive-digital-learning/",
        ]
        now = timezone.now()
        for day_offset in range(90):
            visit_count = 3 + (day_offset % 6)
            visited_day = now - timedelta(days=day_offset)
            for visit_index in range(visit_count):
                visit = SiteVisit.objects.create(
                    path=paths[(day_offset + visit_index) % len(paths)],
                    session_key=f"seed-{day_offset:02d}-{visit_index % 5:02d}",
                    referrer="https://www.google.com/" if visit_index % 3 == 0 else "",
                    user_agent="AfriLearnTech demo analytics",
                )
                SiteVisit.objects.filter(pk=visit.pk).update(
                    visited_at=visited_day.replace(
                        hour=8 + (visit_index % 10),
                        minute=(visit_index * 7) % 60,
                        second=0,
                        microsecond=0,
                    )
                )

    @transaction.atomic
    def handle(self, *args, **options):
        speakers = self.seed_speakers()
        webinars = self.seed_webinars(speakers)
        self.seed_registrations(webinars)
        self.seed_surveys(webinars)
        self.seed_communications()
        if not options["skip_visits"]:
            self.seed_visits()

        self.stdout.write(
            self.style.SUCCESS(
                "Seed data ready: "
                f"{Speaker.objects.count()} speakers, "
                f"{Webinar.objects.count()} webinars, "
                f"{WebinarRegistration.objects.count()} registrations, "
                f"{Survey.objects.count()} surveys, and "
                f"{SiteVisit.objects.count()} visits."
            )
        )
