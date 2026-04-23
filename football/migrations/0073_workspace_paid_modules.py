from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0072_stripe_billing"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspace",
            name="paid_modules",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

