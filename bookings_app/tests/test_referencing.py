from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from dateutil.relativedelta import relativedelta
from rooms.models import Room
from bookings_app.models import ReferencingApplication
from bookings_app.management.commands.purge_referencing_data import Command as PurgeCommand

class TenantReferencingTests(TestCase):
    def setUp(self):
        self.landlord = User.objects.create_user(username='landlord', email='landlord@neoscape.com', password='password')
        self.room = Room.objects.create(
            name='Room 101',
            type='villa',
            price=1200.00,
            location='NeoScape House',
            max_guests=4,
            bedrooms=2,
            bathrooms=2,
            size=120,
            available=True
        )

    def test_referencing_creation_and_defaults(self):
        """Test default values on creation of referencing application."""
        app = ReferencingApplication.objects.create(
            token='test_token_123',
            property_room=self.room,
            landlord_user=self.landlord,
            applicant_name='John Doe',
            applicant_email='john@example.com'
        )
        self.assertEqual(app.status, 'invited')
        self.assertEqual(app.decision, 'pending')
        self.assertFalse(app.ccj_iva_found)
        self.assertEqual(app.missed_payments, 0)
        self.assertFalse(app.is_archived_or_deleted)

    def test_gdpr_purge_logic(self):
        """Verify that eligible data is deleted and active/recent disputes are retained."""
        now = timezone.now()
        
        # App 1: Tenancy ended 13 months ago (Eligible for deletion)
        app_ended_long_ago = ReferencingApplication.objects.create(
            token='token_ended_long_ago',
            property_room=self.room,
            landlord_user=self.landlord,
            applicant_name='Old Tenant',
            applicant_email='old@example.com',
            tenancy_end_date=(now - relativedelta(months=13)).date(),
            legal_dispute_active=False
        )

        # App 2: Tenancy ended 3 months ago (Should NOT be deleted)
        app_ended_recent = ReferencingApplication.objects.create(
            token='token_ended_recent',
            property_room=self.room,
            landlord_user=self.landlord,
            applicant_name='Recent Tenant',
            applicant_email='recent@example.com',
            tenancy_end_date=(now - relativedelta(months=3)).date(),
            legal_dispute_active=False
        )

        # App 3: Tenancy ended 13 months ago but has active legal dispute (Should NOT be deleted)
        app_active_dispute = ReferencingApplication.objects.create(
            token='token_active_dispute',
            property_room=self.room,
            landlord_user=self.landlord,
            applicant_name='Dispute Tenant',
            applicant_email='dispute@example.com',
            tenancy_end_date=(now - relativedelta(months=13)).date(),
            legal_dispute_active=True
        )

        # App 4: Legal dispute resolved 7 months ago (Eligible for deletion)
        app_dispute_resolved = ReferencingApplication.objects.create(
            token='token_dispute_resolved',
            property_room=self.room,
            landlord_user=self.landlord,
            applicant_name='Resolved Tenant',
            applicant_email='resolved@example.com',
            legal_dispute_active=False,
            resolved_at=now - relativedelta(months=7)
        )

        # App 5: Legal dispute resolved 2 months ago (Should NOT be deleted)
        app_dispute_resolved_recent = ReferencingApplication.objects.create(
            token='token_dispute_resolved_recent',
            property_room=self.room,
            landlord_user=self.landlord,
            applicant_name='Resolved Recent Tenant',
            applicant_email='resolved_recent@example.com',
            legal_dispute_active=False,
            resolved_at=now - relativedelta(months=2)
        )

        # Run purge command
        cmd = PurgeCommand()
        cmd.handle()

        # Check outcomes
        self.assertFalse(ReferencingApplication.objects.filter(id=app_ended_long_ago.id).exists())
        self.assertTrue(ReferencingApplication.objects.filter(id=app_ended_recent.id).exists())
        self.assertTrue(ReferencingApplication.objects.filter(id=app_active_dispute.id).exists())
        self.assertFalse(ReferencingApplication.objects.filter(id=app_dispute_resolved.id).exists())
        self.assertTrue(ReferencingApplication.objects.filter(id=app_dispute_resolved_recent.id).exists())
