from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('football', '0054_team_cover_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspacecompetitioncontext',
            name='external_source_url',
            field=models.URLField(
                blank=True,
                help_text='URL pública (Universo/Preferente/etc.) para revalidar el contexto.',
            ),
        ),
    ]

