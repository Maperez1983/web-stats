from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0055_workspacecompetitioncontext_external_source_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspace",
            name="trial_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workspace",
            name="subscription_status",
            field=models.CharField(
                default="trial",
                help_text="trial|active|past_due|canceled|expired",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="workspace",
            name="plan_key",
            field=models.CharField(
                blank=True,
                help_text="Identificador interno del plan (ej: basic, pro).",
                max_length=40,
            ),
        ),
    ]

