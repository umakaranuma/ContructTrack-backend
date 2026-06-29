import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        ('sites', '0001_initial'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('report_type', models.CharField(
                    choices=[
                        ('material_consumption', 'Material Consumption'), ('attendance_log', 'Attendance Log'),
                        ('monthly_spend', 'Monthly Spend'), ('bank_loan', 'Bank Loan Report'),
                        ('custom', 'Custom'), ('subcontractor', 'Subcontractor'),
                    ],
                    max_length=30
                )),
                ('date_from', models.DateField()),
                ('date_to', models.DateField()),
                ('format', models.CharField(
                    choices=[('pdf', 'PDF'), ('excel', 'Excel')],
                    default='pdf', max_length=10
                )),
                ('file_url', models.URLField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('generating', 'Generating'), ('ready', 'Ready'), ('failed', 'Failed')],
                    default='pending', max_length=20
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reports', to='tenants.tenant',
                )),
                ('site', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reports', to='sites.site',
                )),
                ('generated_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'ct_reports', 'ordering': ['-created_at']},
        ),
    ]
