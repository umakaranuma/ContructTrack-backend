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
            name='Bill',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('supplier_name', models.CharField(max_length=255)),
                ('material_type', models.CharField(
                    choices=[('cement', 'Cement'), ('sand', 'Sand'), ('steel', 'Steel'),
                             ('blocks', 'Blocks'), ('aggregate', 'Aggregate'), ('other', 'Other')],
                    max_length=30
                )),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=10)),
                ('unit', models.CharField(max_length=50)),
                ('unit_price_lkr', models.DecimalField(decimal_places=2, max_digits=12)),
                ('total_amount_lkr', models.DecimalField(decimal_places=2, max_digits=14)),
                ('payment_method', models.CharField(
                    choices=[('cash', 'Cash'), ('credit', 'Credit'), ('bank_transfer', 'Bank Transfer')],
                    default='cash', max_length=20
                )),
                ('purpose', models.CharField(
                    choices=[('foundation', 'Foundation'), ('columns', 'Columns'), ('slab', 'Slab'),
                             ('walls', 'Walls'), ('finishing', 'Finishing'), ('other', 'Other')],
                    default='other', max_length=30
                )),
                ('delivery_vehicle_no', models.CharField(blank=True, max_length=20, null=True)),
                ('bill_photo_url', models.URLField()),
                ('photo_gps_lat', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('photo_gps_lng', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('photo_taken_at', models.DateTimeField(blank=True, null=True)),
                ('log_date', models.DateField()),
                ('is_synced', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bills', to='sites.site',
                )),
                ('logged_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='logged_bills', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'ct_bills', 'ordering': ['-log_date', '-created_at']},
        ),
    ]
