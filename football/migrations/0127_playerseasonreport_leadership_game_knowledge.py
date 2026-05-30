from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0126_match_staff_captain_staff_mvp'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerseasonreport',
            name='leadership_rating',
            field=models.PositiveSmallIntegerField(blank=True, help_text='1-10 (opcional)', null=True),
        ),
        migrations.AddField(
            model_name='playerseasonreport',
            name='game_knowledge_rating',
            field=models.PositiveSmallIntegerField(blank=True, help_text='1-10 (opcional)', null=True),
        ),
    ]
