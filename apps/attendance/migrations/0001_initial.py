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
            name='Worker',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('full_name', models.CharField(max_length=255)),
                ('role', models.CharField(max_length=100)),
                ('nic', models.CharField(blank=True, max_length=30, null=True)),
                ('phone', models.CharField(blank=True, max_length=20, null=True)),
                ('daily_rate_lkr', models.DecimalField(decimal_places=2, max_digits=10)),
                ('contract_type', models.CharField(
                    choices=[('daily', 'Daily Rate'), ('monthly', 'Monthly Rate')],
                    default='daily', max_length=20
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='workers', to='sites.site',
                )),
            ],
            options={'db_table': 'ct_workers', 'ordering': ['full_name']},
        ),
        migrations.CreateModel(
            name='DailyAttendance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('log_date', models.DateField()),
                ('status', models.CharField(
                    choices=[('present', 'Present'), ('half', 'Half Day'), ('absent', 'Absent')],
                    default='present', max_length=10
                )),
                ('overtime_hours', models.DecimalField(decimal_places=1, default=0, max_digits=4)),
                ('daily_rate_lkr', models.DecimalField(decimal_places=2, max_digits=10)),
                ('total_earned_lkr', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('is_paid', models.BooleanField(default=False)),
                ('is_rain_day', models.BooleanField(default=False)),
                ('is_synced', models.BooleanField(default=True)),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_records', to='sites.site',
                )),
                ('worker', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance', to='attendance.worker',
                )),
                ('logged_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='logged_attendance', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'ct_daily_attendance',
                'ordering': ['-log_date'],
                'unique_together': {('site', 'worker', 'log_date')},
            },
        ),
        migrations.CreateModel(
            name='AttendanceSummary',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('log_date', models.DateField()),
                ('total_present', models.PositiveIntegerField(default=0)),
                ('total_half', models.PositiveIntegerField(default=0)),
                ('total_absent', models.PositiveIntegerField(default=0)),
                ('total_wage_lkr', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('is_synced', models.BooleanField(default=True)),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_summaries', to='sites.site',
                )),
                ('submitted_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'ct_attendance_summaries',
                'ordering': ['-log_date'],
                'unique_together': {('site', 'log_date')},
            },
        ),
    ]
