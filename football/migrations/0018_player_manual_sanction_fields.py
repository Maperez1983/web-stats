from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0017_convocationrecord_lineup_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='manual_sanction_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='player',
            name='manual_sanction_reason',
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name='player',
            name='manual_sanction_until',
            field=models.DateField(blank=True, null=True),
        ),
    ]
