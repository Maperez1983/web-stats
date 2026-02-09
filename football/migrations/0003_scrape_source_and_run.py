from django.db import migrations, models
import django.db.models.deletion


def create_default_sources(apps, schema_editor):
    ScrapeSource = apps.get_model('football', 'ScrapeSource')
    ScrapeSource.objects.create(
        name='División de Honor Andaluza · Grupo 2',
        url='https://www.lapreferente.com/C22273-1/division-honor-andaluza-gr2/estadisticas.html',
        is_active=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0002_matchevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScrapeSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('url', models.URLField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Fuente de scraping',
                'verbose_name_plural': 'Fuentes de scraping',
            },
        ),
        migrations.CreateModel(
            name='ScrapeRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('running', 'En ejecución'), ('success', 'Completado'), ('error', 'Error')], default='running', max_length=12)),
                ('message', models.TextField(blank=True)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='runs', to='football.scrapesource')),
            ],
            options={
                'ordering': ['-started_at'],
                'verbose_name': 'Ejecución de scraping',
                'verbose_name_plural': 'Ejecuciones de scraping',
            },
        ),
        migrations.RunPython(create_default_sources),
    ]
