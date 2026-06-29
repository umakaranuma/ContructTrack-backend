"""
Initial migration for the accounts app.
Creates ct_users table — the sole user store for ConstructTrack.
"""
import uuid
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('full_name', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('phone', models.CharField(blank=True, max_length=20, null=True)),
                ('user_type', models.CharField(
                    choices=[('admin', 'Admin'), ('owner', 'Owner'), ('manager', 'Manager')],
                    default='owner', max_length=20
                )),
                ('admin_role', models.CharField(
                    blank=True,
                    choices=[('super_admin', 'Super Admin'), ('support', 'Support'), ('finance', 'Finance')],
                    max_length=20, null=True
                )),
                ('reference_code', models.CharField(blank=True, max_length=20, null=True, unique=True)),
                ('nic', models.CharField(blank=True, max_length=30, null=True)),
                ('profile_photo_url', models.URLField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_suspended', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'ct_users',
            },
        ),
    ]
