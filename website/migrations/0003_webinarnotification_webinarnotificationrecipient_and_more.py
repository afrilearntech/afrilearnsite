# Generated for the Django 5.2 project on 2026-09-28.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0002_speaker_survey_sitevisit_surveyquestion_webinar_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WebinarNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('audience', models.CharField(choices=[('active', 'All active registrations'), ('registered', 'Registered'), ('attended', 'Attended'), ('no_show', 'No show'), ('cancelled', 'Cancelled')], max_length=20)),
                ('subject', models.CharField(max_length=240)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('sending', 'Sending'), ('sent', 'Sent'), ('partial', 'Partially sent'), ('failed', 'Failed')], default='sending', max_length=20)),
                ('recipient_count', models.PositiveIntegerField(default=0)),
                ('delivered_count', models.PositiveIntegerField(default=0)),
                ('failed_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='webinar_notifications', to=settings.AUTH_USER_MODEL)),
                ('webinar', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='website.webinar')),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='WebinarNotificationRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=201)),
                ('email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='website.webinarnotification')),
                ('registration', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_deliveries', to='website.webinarregistration')),
            ],
            options={
                'ordering': ('email',),
            },
        ),
        migrations.AddIndex(
            model_name='webinarnotification',
            index=models.Index(fields=['webinar', 'created_at'], name='website_web_webinar_d5de31_idx'),
        ),
        migrations.AddIndex(
            model_name='webinarnotificationrecipient',
            index=models.Index(fields=['notification', 'status'], name='website_web_notific_e99655_idx'),
        ),
    ]
