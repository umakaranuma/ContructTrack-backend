"""
Custom User model — completely replaces Django's auth.User.
We use AbstractBaseUser (not AbstractUser) to avoid inheriting fields
like last_name, date_joined, groups, user_permissions that we don't need
and that would create foreign keys to auth_* tables we've disabled.
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


class UserManager(BaseUserManager):
    """
    Custom manager because email is the USERNAME_FIELD, not 'username'.
    Also no groups/permissions plumbing needed.
    """

    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        """
        Used only for manage.py createsuperuser — creates an admin type user.
        We can't use Django's built-in is_staff/is_superuser flags because the
        auth tables are disabled; user_type='admin' with admin_role='super_admin'
        is our equivalent.
        """
        extra_fields.setdefault('user_type', 'admin')
        extra_fields.setdefault('admin_role', 'super_admin')
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, full_name, password, **extra_fields)


class User(AbstractBaseUser):
    """
    Single User table for all roles: admin (ConstructTrack staff),
    owner (company account holder), manager (mobile app user).
    Role-specific behaviour is handled by permission classes, not separate tables.
    """

    USER_TYPE_CHOICES = [
        ('admin', 'Admin'),      # ConstructTrack internal staff
        ('owner', 'Owner'),      # Tenant company owner (web dashboard)
        ('manager', 'Manager'),  # Site manager (mobile app)
    ]

    ADMIN_ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),  # full platform control
        ('support', 'Support'),          # read + limited write
        ('finance', 'Finance'),          # payments module only
    ]

    # UUID PK — prevents enumeration and works well with offline-first mobile sync
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    full_name = models.CharField(max_length=255)

    # Email doubles as the login username — unique globally across all user types
    email = models.EmailField(unique=True)

    phone = models.CharField(max_length=20, blank=True, null=True)

    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='owner')

    # admin_role is only populated when user_type == 'admin'
    admin_role = models.CharField(
        max_length=20,
        choices=ADMIN_ROLE_CHOICES,
        blank=True,
        null=True,
        help_text='Set only for admin-type users; null for owners and managers.'
    )

    # reference_code is auto-generated for managers so owners can look them up
    # without knowing their email (e.g. a manager gives the owner "MGR-4821")
    reference_code = models.CharField(max_length=20, unique=True, blank=True, null=True)

    nic = models.CharField(max_length=30, blank=True, null=True)  # national ID — Sri Lanka
    profile_photo_url = models.URLField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_suspended = models.BooleanField(
        default=False,
        help_text='Soft-disable without deleting — preserves audit trail.'
    )

    # AbstractBaseUser provides: password, last_login (we use it), is_anonymous
    # We do NOT add: groups, user_permissions, is_staff, is_superuser

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']  # asked by createsuperuser command

    objects = UserManager()

    class Meta:
        db_table = 'ct_users'   # explicit table name to avoid 'accounts_user'

    def __str__(self):
        return f"{self.full_name} <{self.email}> [{self.user_type}]"

    # AbstractBaseUser requires these — we implement them without the auth tables
    @property
    def is_staff(self):
        # Needed by Django's admin check machinery even though we don't use admin
        return self.user_type == 'admin'

    def has_perm(self, perm, obj=None):
        # We don't use Django's permission system; always return True for active admins
        return self.user_type == 'admin' and self.is_active

    def has_module_perms(self, app_label):
        return self.user_type == 'admin' and self.is_active
