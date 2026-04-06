from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0053_multiteam_competition_context"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="cover_image",
            field=models.ImageField(blank=True, null=True, upload_to="team-covers/"),
        ),
        migrations.AddField(
            model_name="team",
            name="cover_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

