from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0073_workspace_paid_modules"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportedSessionDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("repository", models.CharField(choices=[("traditional", "Clásicas"), ("interactive", "Interactivas")], default="traditional", max_length=20)),
                ("title", models.CharField(max_length=180)),
                ("session_date", models.DateField(blank=True, null=True)),
                ("pdf", models.FileField(upload_to="imported-sessions-pdf/")),
                ("preview_image", models.ImageField(blank=True, null=True, upload_to="imported-sessions-preview/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="imported_session_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="imported_session_documents",
                        to="football.team",
                    ),
                ),
            ],
            options={
                "ordering": ["-session_date", "-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="importedsessiondocument",
            index=models.Index(fields=["team", "repository", "-created_at"], name="football_imp_team_r_7fc531_idx"),
        ),
        migrations.AddIndex(
            model_name="importedsessiondocument",
            index=models.Index(fields=["team", "repository", "-session_date"], name="football_imp_team_r_a6aa9f_idx"),
        ),
    ]
