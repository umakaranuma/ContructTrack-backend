"""
Management command to seed all development data.
Run: python manage.py seed_all

WARNING: Development use only. Rotate all credentials before any staging/production deployment.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import random
import string


class Command(BaseCommand):
    help = 'Seeds all development data — packages, admin users, tenants, sites, workers, logs'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting seed process...\n')

        self._seed_packages()
        self.stdout.write(self.style.SUCCESS('[OK] Packages seeded'))

        self._seed_admin_users()
        self.stdout.write(self.style.SUCCESS('[OK] Admin users seeded'))

        self._seed_tenants()
        self.stdout.write(self.style.SUCCESS('[OK] Tenants seeded'))

        self._seed_sites()
        self.stdout.write(self.style.SUCCESS('[OK] Sites seeded'))

        self._seed_mobile_users()
        self.stdout.write(self.style.SUCCESS('[OK] Mobile users seeded'))

        self._seed_workers()
        self.stdout.write(self.style.SUCCESS('[OK] Workers seeded'))

        self._seed_logs()
        self.stdout.write(self.style.SUCCESS('[OK] Sample logs seeded'))

        self.stdout.write('\n' + self.style.SUCCESS('All seed data loaded successfully.'))

        # Print summary
        from apps.accounts.models import User
        from apps.tenants.models import Tenant
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Tenants: {Tenant.objects.count()}')

    # -------------------------------------------------------------------------
    # Packages
    # -------------------------------------------------------------------------
    def _seed_packages(self):
        from apps.tenants.models import Package

        packages = [
            {
                'name': 'Lite',
                'price_lkr': 7500.00,
                'max_sites': 2,
                'max_managers': 2,
                'trial_days': 7,
                'feature_excel': False,
                'feature_whatsapp': False,
                'feature_bill_gps': True,
                'feature_theft_alerts': False,
                'feature_bank_report': False,
                'feature_branded_pdf': False,
                'feature_subcontractor': False,
                'display_order': 1,
            },
            {
                'name': 'Pro',
                'price_lkr': 20000.00,
                'max_sites': 6,
                'max_managers': 6,
                'trial_days': 7,
                'feature_excel': True,
                'feature_whatsapp': True,
                'feature_bill_gps': True,
                'feature_theft_alerts': True,
                'feature_bank_report': False,
                'feature_branded_pdf': False,
                'feature_subcontractor': False,
                'display_order': 2,
            },
            {
                'name': 'Enterprise',
                'price_lkr': 50000.00,
                'max_sites': 9999,      # 9999 = effectively unlimited (UNSIGNED column)
                'max_managers': 9999,   # 9999 = effectively unlimited
                'trial_days': 14,
                'feature_excel': True,
                'feature_whatsapp': True,
                'feature_bill_gps': True,
                'feature_theft_alerts': True,
                'feature_bank_report': True,
                'feature_branded_pdf': True,
                'feature_subcontractor': True,
                'display_order': 3,
            },
        ]

        for pkg_data in packages:
            Package.objects.get_or_create(name=pkg_data['name'], defaults=pkg_data)

    # -------------------------------------------------------------------------
    # Admin Users (ConstructTrack internal staff)
    # -------------------------------------------------------------------------
    def _seed_admin_users(self):
        from apps.accounts.models import User

        admins = [
            {
                'full_name': 'Rajan Perera',
                'email': 'superadmin@constructtrack.lk',
                'password': 'Admin@CT2025!',
                'user_type': 'admin',
                'admin_role': 'super_admin',
            },
            {
                'full_name': 'Amali Fernando',
                'email': 'support@constructtrack.lk',
                'password': 'Support@CT2025!',
                'user_type': 'admin',
                'admin_role': 'support',
            },
            {
                'full_name': 'Lakshan Bandara',
                'email': 'finance@constructtrack.lk',
                'password': 'Finance@CT2025!',
                'user_type': 'admin',
                'admin_role': 'finance',
            },
        ]

        for admin_data in admins:
            password = admin_data.pop('password')
            user, created = User.objects.get_or_create(
                email=admin_data['email'],
                defaults=admin_data,
            )
            if created:
                user.set_password(password)
                user.save()

    # -------------------------------------------------------------------------
    # Tenants (Paying companies)
    # -------------------------------------------------------------------------
    def _seed_tenants(self):
        from apps.accounts.models import User
        from apps.tenants.models import Package, Tenant

        tenants_data = [
            {
                'company_name': 'BuildPro (Pvt) Ltd',
                'package_name': 'Enterprise',
                'status': 'active',
                'subscription_start': date(2025, 1, 1),
                'subscription_end': date(2025, 12, 31),
                'owner': {
                    'full_name': 'Chaminda Wickramasinghe',
                    'email': 'owner@buildpro.lk',
                    'password': 'Owner@BP2025!',
                    'phone': '+94771234567',
                    'user_type': 'owner',
                },
                'whatsapp_alerts': True,
                'whatsapp_number': '+94771234567',
                'email_digest': 'daily',
            },
            {
                'company_name': 'Skyline Constructions',
                'package_name': 'Pro',
                'status': 'active',
                'subscription_start': date(2025, 3, 1),
                'subscription_end': date(2025, 8, 31),
                'owner': {
                    'full_name': 'Dinesh Samaraweera',
                    'email': 'owner@skyline.lk',
                    'password': 'Owner@SL2025!',
                    'phone': '+94719876543',
                    'user_type': 'owner',
                },
                'whatsapp_alerts': True,
                'whatsapp_number': '+94719876543',
                'email_digest': 'weekly',
            },
            {
                'company_name': 'HomeCraft Builders',
                'package_name': 'Lite',
                'status': 'trial',
                'trial_start': date(2025, 6, 12),
                'trial_end': date(2025, 6, 19),
                'subscription_start': None,
                'subscription_end': None,
                'owner': {
                    'full_name': 'Sanduni Rathnayake',
                    'email': 'owner@homecraft.lk',
                    'password': 'Owner@HC2025!',
                    'phone': '+94762345678',
                    'user_type': 'owner',
                },
                'whatsapp_alerts': False,
                'whatsapp_number': None,
                'email_digest': 'daily',
            },
        ]

        for t in tenants_data:
            # Create or get the owner user
            owner_data = t.pop('owner')
            password = owner_data.pop('password')
            owner, created = User.objects.get_or_create(
                email=owner_data['email'],
                defaults=owner_data,
            )
            if created:
                owner.set_password(password)
                owner.save()

            package = Package.objects.get(name=t.pop('package_name'))

            Tenant.objects.get_or_create(
                company_name=t['company_name'],
                defaults={
                    'owner': owner,
                    'package': package,
                    'status': t.get('status', 'active'),
                    'subscription_start': t.get('subscription_start'),
                    'subscription_end': t.get('subscription_end'),
                    'trial_start': t.get('trial_start'),
                    'trial_end': t.get('trial_end'),
                    'whatsapp_alerts': t.get('whatsapp_alerts', False),
                    'whatsapp_number': t.get('whatsapp_number'),
                    'email_digest': t.get('email_digest', 'off'),
                },
            )

    # -------------------------------------------------------------------------
    # Sites
    # -------------------------------------------------------------------------
    def _seed_sites(self):
        from apps.tenants.models import Tenant
        from apps.sites.models import Site

        buildpro = Tenant.objects.get(company_name='BuildPro (Pvt) Ltd')
        skyline = Tenant.objects.get(company_name='Skyline Constructions')

        sites_data = [
            # BuildPro sites
            {
                'tenant': buildpro,
                'name': 'Colombo Site A — Commercial Tower',
                'address': 'No. 45, Galle Road, Colombo 03',
                'project_type': 'commercial',
                'current_stage': 'columns',
                'budget_lkr': 85000000,
                'start_date': date(2025, 1, 15),
                'end_date': date(2026, 6, 30),
            },
            {
                'tenant': buildpro,
                'name': 'Kandy Site B — Residential Complex',
                'address': 'Peradeniya Road, Kandy',
                'project_type': 'residential',
                'current_stage': 'upper_slab',
                'budget_lkr': 42000000,
                'start_date': date(2025, 2, 1),
                'end_date': date(2025, 11, 30),
            },
            {
                'tenant': buildpro,
                'name': 'Galle Site C — Boutique Hotel',
                'address': 'Unawatuna Road, Galle',
                'project_type': 'commercial',
                'current_stage': 'foundation',
                'budget_lkr': 120000000,
                'start_date': date(2025, 4, 1),
                'end_date': date(2026, 12, 31),
            },
            # Skyline sites
            {
                'tenant': skyline,
                'name': 'Negombo Site — Housing Scheme',
                'address': 'Old Negombo Road, Ja-Ela',
                'project_type': 'residential',
                'current_stage': 'walls',
                'budget_lkr': 28000000,
                'start_date': date(2025, 3, 10),
                'end_date': date(2025, 10, 31),
            },
            {
                'tenant': skyline,
                'name': 'Nugegoda Office Block',
                'address': 'High Level Road, Nugegoda',
                'project_type': 'commercial',
                'current_stage': 'beams',
                'budget_lkr': 55000000,
                'start_date': date(2025, 2, 15),
                'end_date': date(2026, 2, 28),
            },
        ]

        for site_data in sites_data:
            Site.objects.get_or_create(
                tenant=site_data['tenant'],
                name=site_data['name'],
                defaults=site_data,
            )

    # -------------------------------------------------------------------------
    # Mobile Users (Site Managers)
    # -------------------------------------------------------------------------
    def _seed_mobile_users(self):
        from apps.accounts.models import User
        from apps.sites.models import Site, SiteManager

        managers_data = [
            {
                'full_name': 'Kamal Perera',
                'email': 'kamal@manager.lk',
                'password': 'Manager@1234!',
                'phone': '+94771111001',
                'reference_code': 'MGR-1001',
                'user_type': 'manager',
                'sites': ['Colombo Site A — Commercial Tower', 'Kandy Site B — Residential Complex'],
            },
            {
                'full_name': 'Suresh Fernando',
                'email': 'suresh@manager.lk',
                'password': 'Manager@1234!',
                'phone': '+94771111002',
                'reference_code': 'MGR-1002',
                'user_type': 'manager',
                'sites': ['Galle Site C — Boutique Hotel'],
            },
            {
                'full_name': 'Priya Kumari',
                'email': 'priya@manager.lk',
                'password': 'Manager@1234!',
                'phone': '+94771111003',
                'reference_code': 'MGR-1003',
                'user_type': 'manager',
                'sites': ['Negombo Site — Housing Scheme'],
            },
            {
                'full_name': 'Nimal Jayasuriya',
                'email': 'nimal@manager.lk',
                'password': 'Manager@1234!',
                'phone': '+94771111004',
                'reference_code': 'MGR-1004',
                'user_type': 'manager',
                'sites': ['Nugegoda Office Block'],
            },
        ]

        for mgr_data in managers_data:
            site_names = mgr_data.pop('sites')
            password = mgr_data.pop('password')

            user, created = User.objects.get_or_create(
                email=mgr_data['email'],
                defaults=mgr_data,
            )
            if created:
                user.set_password(password)
                user.save()

            # Assign to sites
            for site_name in site_names:
                try:
                    site = Site.objects.get(name=site_name)
                    SiteManager.objects.get_or_create(
                        site=site,
                        manager=user,
                        defaults={'is_active': True},
                    )
                except Site.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  Site not found: {site_name}'))

    # -------------------------------------------------------------------------
    # Workers (labour roster for Colombo Site A)
    # -------------------------------------------------------------------------
    def _seed_workers(self):
        from apps.sites.models import Site
        from apps.attendance.models import Worker

        try:
            site = Site.objects.get(name='Colombo Site A — Commercial Tower')
        except Site.DoesNotExist:
            self.stdout.write(self.style.WARNING('Colombo Site A not found; skipping workers.'))
            return

        workers = [
            {'full_name': 'Roshan Silva',      'role': 'mason',      'daily_rate_lkr': 4500},
            {'full_name': 'Anura Dissanayake', 'role': 'mason',      'daily_rate_lkr': 4500},
            {'full_name': 'Sampath Kodikara',  'role': 'helper',     'daily_rate_lkr': 3200},
            {'full_name': 'Thilina Rajapaksa', 'role': 'helper',     'daily_rate_lkr': 3200},
            {'full_name': 'Mahinda Kurera',    'role': 'bar_bender', 'daily_rate_lkr': 4800},
            {'full_name': 'Chamara Wijesinghe','role': 'carpenter',  'daily_rate_lkr': 4500},
            {'full_name': 'Lasith Madushanka', 'role': 'operator',   'daily_rate_lkr': 5500},
            {'full_name': 'Nuwan Pradeep',     'role': 'labourer',   'daily_rate_lkr': 2800},
            {'full_name': 'Dimuthu Siriwardena','role': 'labourer',  'daily_rate_lkr': 2800},
            {'full_name': 'Kasun Pathirana',   'role': 'labourer',   'daily_rate_lkr': 2800},
        ]

        for w in workers:
            Worker.objects.get_or_create(
                site=site,
                full_name=w['full_name'],
                defaults={**w, 'contract_type': 'daily', 'is_active': True},
            )

    # -------------------------------------------------------------------------
    # Sample Bills & Payments
    # -------------------------------------------------------------------------
    def _seed_logs(self):
        from apps.accounts.models import User
        from apps.sites.models import Site
        from apps.bills.models import Bill
        from apps.payments.models import Payment
        from apps.tenants.models import Tenant, Package

        try:
            kamal = User.objects.get(email='kamal@manager.lk')
            colombo_a = Site.objects.get(name='Colombo Site A — Commercial Tower')
            kandy_b = Site.objects.get(name='Kandy Site B — Residential Complex')
        except (User.DoesNotExist, Site.DoesNotExist):
            self.stdout.write(self.style.WARNING('Required objects not found; skipping logs.'))
            return

        bills = [
            {
                'site': colombo_a,
                'logged_by': kamal,
                'supplier_name': 'Tokyo Cement Dealers',
                'material_type': 'cement',
                'quantity': 50,
                'unit': 'bags',
                'unit_price_lkr': 2450,
                'total_amount_lkr': 122500,
                'payment_method': 'credit',
                'purpose': 'columns',
                'log_date': date(2025, 6, 17),
            },
            {
                'site': colombo_a,
                'logged_by': kamal,
                'supplier_name': 'Kelani Cables & Steel',
                'material_type': 'steel',
                'quantity': 500,
                'unit': 'kg',
                'unit_price_lkr': 320,
                'total_amount_lkr': 160000,
                'payment_method': 'bank_transfer',
                'purpose': 'columns',
                'log_date': date(2025, 6, 17),
            },
            {
                'site': kandy_b,
                'logged_by': kamal,
                'supplier_name': 'Kandy Sand & Gravel',
                'material_type': 'sand',
                'quantity': 5,
                'unit': 'loads',
                'unit_price_lkr': 18000,
                'total_amount_lkr': 90000,
                'payment_method': 'cash',
                'purpose': 'upper_slab',
                'log_date': date(2025, 6, 17),
            },
        ]

        for b in bills:
            Bill.objects.get_or_create(
                site=b['site'],
                supplier_name=b['supplier_name'],
                log_date=b['log_date'],
                defaults=b,
            )

        # Seed payments
        superadmin = User.objects.get(email='superadmin@constructtrack.lk')
        buildpro = Tenant.objects.get(company_name='BuildPro (Pvt) Ltd')
        skyline = Tenant.objects.get(company_name='Skyline Constructions')
        enterprise_pkg = Package.objects.get(name='Enterprise')
        pro_pkg = Package.objects.get(name='Pro')

        payments = [
            {
                'tenant': buildpro,
                'package': enterprise_pkg,
                'amount_lkr': 50000,
                'method': 'payhere',
                'gateway_ref': 'PH-2025-001234',
                'status': 'success',
                'payment_date': date(2025, 1, 1),
                'validity_months': 12,
                'recorded_by': superadmin,
            },
            {
                'tenant': skyline,
                'package': pro_pkg,
                'amount_lkr': 20000,
                'method': 'bank_transfer',
                'gateway_ref': 'BOC-2025-TRF-8871',
                'status': 'success',
                'payment_date': date(2025, 3, 1),
                'validity_months': 6,
                'recorded_by': superadmin,
            },
        ]

        for p in payments:
            Payment.objects.get_or_create(
                tenant=p['tenant'],
                gateway_ref=p.get('gateway_ref'),
                defaults=p,
            )
