from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0037_workspacecompetitioncontext_workspacecompetitionsnapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='crest_image',
            field=models.ImageField(blank=True, null=True, upload_to='team-crests/'),
        ),
        migrations.AddField(
            model_name='team',
            name='crest_url',
            field=models.URLField(blank=True, help_text='URL sincronizada del escudo del equipo'),
        ),
    ]
