from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("football", "0042_sharelink_access_count_sharelink_created_by_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="photo_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

