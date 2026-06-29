import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Package',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('price_lkr', models.DecimalField(decimal_places=2, max_digits=10)),
                ('max_sites', models.PositiveIntegerField(default=1)),
                ('max_managers', models.PositiveIntegerField(default=2)),
                ('trial_days', models.PositiveIntegerField(default=14)),
                ('feature_excel', models.BooleanField(default=True)),
                ('feature_whatsapp', models.BooleanField(default=False)),
                ('feature_bill_gps', models.BooleanField(default=True)),
                ('feature_theft_alerts', models.BooleanField(default=False)),
                ('feature_bank_report', models.BooleanField(default=False)),
                ('feature_branded_pdf', models.BooleanField(default=False)),
                ('feature_subcontractor', models.BooleanField(default=False)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'db_table': 'ct_packages', 'ordering': ['display_order']},
        ),
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('company_name', models.CharField(max_length=255)),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('trial', 'Trial'), ('expired', 'Expired'), ('suspended', 'Suspended')],
                    default='trial', max_length=20
                )),
                ('subscription_start', models.DateTimeField(blank=True, null=True)),
                ('subscription_end', models.DateTimeField(blank=True, null=True)),
                ('trial_start', models.DateTimeField(blank=True, null=True)),
                ('trial_end', models.DateTimeField(blank=True, null=True)),
                ('logo_url', models.URLField(blank=True, null=True)),
                ('address', models.TextField(blank=True, null=True)),
                ('contact_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('contact_phone', models.CharField(blank=True, max_length=20, null=True)),
                ('whatsapp_alerts', models.BooleanField(default=False)),
                ('whatsapp_number', models.CharField(blank=True, max_length=20, null=True)),
                ('email_digest', models.CharField(
                    choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('off', 'Off')],
                    default='daily', max_length=10
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='owned_tenants',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('package', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tenants', to='tenants.package',
                )),
            ],
            options={'db_table': 'ct_tenants'},
        ),
        migrations.CreateModel(
            name='TenantSubscriptionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.TextField(blank=True, null=True)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subscription_logs', to='tenants.tenant',
                )),
                ('old_package', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='tenants.package',
                )),
                ('new_package', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='tenants.package',
                )),
                ('changed_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'ct_tenant_subscription_logs', 'ordering': ['-changed_at']},
        ),
    ]
