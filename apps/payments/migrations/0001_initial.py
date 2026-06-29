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
            name='Payment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('amount_lkr', models.DecimalField(decimal_places=2, max_digits=12)),
                ('method', models.CharField(
                    choices=[('payhere', 'PayHere'), ('webxpay', 'Webxpay'),
                             ('bank_transfer', 'Bank Transfer'), ('manual', 'Manual (Admin)')],
                    max_length=20
                )),
                ('gateway_ref', models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ('status', models.CharField(
                    choices=[('success', 'Success'), ('failed', 'Failed'),
                             ('pending', 'Pending'), ('refunded', 'Refunded')],
                    default='pending', max_length=20
                )),
                ('payment_date', models.DateField(blank=True, null=True)),
                ('validity_months', models.PositiveSmallIntegerField(default=1)),
                ('internal_note', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payments', to='tenants.tenant',
                )),
                ('package', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='tenants.package',
                )),
                ('recorded_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'ct_payments', 'ordering': ['-created_at']},
        ),
    ]
