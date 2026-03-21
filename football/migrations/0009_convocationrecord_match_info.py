from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0008_sessiontask_tactical_layout'),
    ]

    operations = [
        migrations.AddField(
            model_name='convocationrecord',
            name='location',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='convocationrecord',
            name='match',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='convocations', to='football.match'),
        ),
        migrations.AddField(
            model_name='convocationrecord',
            name='match_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='convocationrecord',
            name='match_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='convocationrecord',
            name='opponent_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='convocationrecord',
            name='round',
            field=models.CharField(blank=True, max_length=60),
        ),
    ]
