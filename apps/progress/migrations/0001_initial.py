import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sites', '0001_initial'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgressLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('log_date', models.DateField()),
                ('stage', models.CharField(max_length=30)),
                ('work_done_today', models.TextField()),
                ('blockers', models.CharField(
                    blank=True,
                    choices=[
                        ('material_shortage', 'Material Shortage'), ('worker_noshow', 'Workers Did Not Show Up'),
                        ('equipment_fault', 'Equipment Fault'), ('rain', 'Rain'),
                        ('awaiting_owner', 'Awaiting Owner Decision'), ('other', 'Other'),
                    ],
                    max_length=30, null=True
                )),
                ('blocker_note', models.TextField(blank=True, null=True)),
                ('tomorrow_status', models.CharField(
                    choices=[
                        ('working', 'Working'), ('rain_hold', 'Rain Hold'),
                        ('material_wait', 'Waiting for Materials'), ('awaiting_owner', 'Awaiting Owner'),
                    ],
                    default='working', max_length=20
                )),
                ('is_synced', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progress_logs', to='sites.site',
                )),
                ('logged_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='progress_logs', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'ct_progress_logs',
                'ordering': ['-log_date'],
                'unique_together': {('site', 'log_date')},
            },
        ),
        migrations.CreateModel(
            name='ProgressPhoto',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('photo_url', models.URLField()),
                ('gps_lat', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('gps_lng', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('taken_at', models.DateTimeField(blank=True, null=True)),
                ('caption', models.CharField(blank=True, max_length=255, null=True)),
                ('progress_log', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='photos', to='progress.progresslog',
                )),
            ],
            options={'db_table': 'ct_progress_photos', 'ordering': ['taken_at']},
        ),
    ]
