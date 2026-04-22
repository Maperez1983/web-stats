from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0071_video_analysis_pro"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspace",
            name="stripe_customer_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="workspace",
            name="stripe_subscription_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="workspace",
            name="stripe_price_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="workspace",
            name="subscription_current_period_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workspace",
            name="subscription_cancel_at_period_end",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="workspace",
            name="subscription_canceled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="StripeEventLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(db_index=True, max_length=120, unique=True)),
                ("event_type", models.CharField(blank=True, max_length=120)),
                ("ok", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "workspace",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="stripe_events",
                        to="football.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]

