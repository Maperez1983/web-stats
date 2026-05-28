from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0124_team_home_stadium'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='home_stadium_address',
            field=models.CharField(blank=True, help_text='Dirección postal del campo/estadio', max_length=260),
        ),
        migrations.AddField(
            model_name='team',
            name='home_stadium_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='team',
            name='home_stadium_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='team',
            name='home_stadium_maps_url',
            field=models.URLField(blank=True, help_text='Enlace directo a Google Maps u otro mapa'),
        ),
    ]
