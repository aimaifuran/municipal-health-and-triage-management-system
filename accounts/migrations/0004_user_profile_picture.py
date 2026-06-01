# Generated manually for profile picture fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_backfill_doctor_assignments_for_active_triage"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_picture_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="user",
            name="profile_picture_public_id",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
