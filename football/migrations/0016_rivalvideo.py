from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0015_homecarouselimage'),
    ]

    operations = [
        migrations.CreateModel(
            name='RivalVideo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180)),
                ('video', models.FileField(upload_to='rival-videos/')),
                ('source', models.CharField(choices=[('universo', 'Universo RFAF'), ('rfaf', 'RFAF'), ('preferente', 'La Preferente'), ('manual', 'Manual')], default='manual', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('rival_team', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rival_videos', to='football.team')),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
