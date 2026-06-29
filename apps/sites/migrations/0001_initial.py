import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('address', models.TextField(blank=True, null=True)),
                ('project_type', models.CharField(
                    choices=[('residential', 'Residential'), ('commercial', 'Commercial'), ('infrastructure', 'Infrastructure')],
                    default='residential', max_length=30
                )),
                ('current_stage', models.CharField(
                    choices=[
                        ('excavation', 'Excavation'), ('foundation', 'Foundation'),
                        ('ground_slab', 'Ground Slab'), ('columns', 'Columns'),
                        ('beams', 'Beams'), ('upper_slab', 'Upper Slab'),
                        ('walls', 'Walls'), ('roof', 'Roof'),
                        ('finishing', 'Finishing'), ('completed', 'Completed'),
                    ],
                    default='excavation', max_length=30
                )),
                ('budget_lkr', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sites', to='tenants.tenant',
                )),
            ],
            options={'db_table': 'ct_sites', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='SiteManager',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('removed_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='site_managers', to='sites.site',
                )),
                ('manager', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='managed_sites', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'ct_site_managers', 'unique_together': {('site', 'manager')}},
        ),
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('alert_type', models.CharField(
                    choices=[
                        ('material_cap', 'Material Cap Exceeded'), ('missing_log', 'Missing Progress Log'),
                        ('no_bill_photo', 'Bill Without Photo'), ('anomaly', 'Anomaly Detected'),
                    ],
                    max_length=30
                )),
                ('message', models.TextField()),
                ('is_resolved', models.BooleanField(default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alerts', to='sites.site',
                )),
                ('resolved_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'ct_alerts', 'ordering': ['-created_at']},
        ),
    ]
