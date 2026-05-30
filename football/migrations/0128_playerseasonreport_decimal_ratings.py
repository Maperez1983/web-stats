from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0127_playerseasonreport_leadership_game_knowledge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='playerseasonreport',
            name='overall_rating',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='1-10 (opcional)', max_digits=3, null=True),
        ),
        migrations.AlterField(
            model_name='playerseasonreport',
            name='technical_rating',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='1-10 (opcional)', max_digits=3, null=True),
        ),
        migrations.AlterField(
            model_name='playerseasonreport',
            name='tactical_rating',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='1-10 (opcional)', max_digits=3, null=True),
        ),
        migrations.AlterField(
            model_name='playerseasonreport',
            name='physical_rating',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='1-10 (opcional)', max_digits=3, null=True),
        ),
        migrations.AlterField(
            model_name='playerseasonreport',
            name='mental_rating',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='1-10 (opcional)', max_digits=3, null=True),
        ),
        migrations.AlterField(
            model_name='playerseasonreport',
            name='social_rating',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='1-10 (opcional)', max_digits=3, null=True),
        ),
        migrations.AlterField(
            model_name='playerseasonreport',
            name='leadership_rating',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='1-10 (opcional)', max_digits=3, null=True),
        ),
        migrations.AlterField(
            model_name='playerseasonreport',
            name='game_knowledge_rating',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='1-10 (opcional)', max_digits=3, null=True),
        ),
    ]
