import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from bookings_app.models import ReferencingApplication
from core.storage_backends import supabase_storage

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Purges referencing data, documents, and reports after 12 months post-tenancy (or 6 months post-dispute-resolution).'

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()

        # 1. Tenancies ended 12+ months ago with no active legal dispute
        cut_off_12m = today - timedelta(days=365)
        apps_to_purge_tenancy = ReferencingApplication.objects.filter(
            tenancy_end_date__lte=cut_off_12m,
            legal_dispute_active=False,
            is_archived_or_deleted=False
        )

        # 2. Legal dispute resolved 6+ months ago
        cut_off_6m = now - timedelta(days=180)
        apps_to_purge_resolved = ReferencingApplication.objects.filter(
            legal_dispute_active=False,
            resolved_at__lte=cut_off_6m,
            is_archived_or_deleted=False
        )

        # Combine querysets
        apps_to_purge = list(apps_to_purge_tenancy) + list(apps_to_purge_resolved)
        # De-duplicate by ID
        seen_ids = set()
        unique_apps = []
        for app in apps_to_purge:
            if app.id not in seen_ids:
                seen_ids.add(app.id)
                unique_apps.append(app)

        self.stdout.write(self.style.SUCCESS(f"Found {len(unique_apps)} referencing applications eligible for GDPR deletion."))

        deleted_count = 0
        for app in unique_apps:
            # 1. Delete associated uploaded documents from Supabase/Local Storage
            if app.uploaded_documents:
                for doc in app.uploaded_documents:
                    doc_url = doc if isinstance(doc, str) else doc.get('file_url', '')
                    if doc_url:
                        self.delete_storage_file(doc_url)

            # 2. Delete report PDF
            if app.report_pdf_url:
                self.delete_storage_file(app.report_pdf_url)

            # 3. Soft-delete or hard-delete database record (Permanently delete as per instructions)
            app.is_archived_or_deleted = True
            app.save(update_fields=['is_archived_or_deleted'])
            
            # Optionally hard-delete
            app_id = app.id
            app.delete()
            deleted_count += 1
            self.stdout.write(self.style.SUCCESS(f"Permanently purged ReferencingApplication #{app_id} and all its documents."))

        self.stdout.write(self.style.SUCCESS(f"Successfully processed and purged {deleted_count} records."))

    def delete_storage_file(self, file_url):
        """Helper to delete a file from Supabase or local storage based on its URL."""
        if 'supabase.co' in file_url:
            # Extract path from URL
            try:
                # E.g. https://...supabase.co/storage/v1/object/sign/documents/referencing_reports/abc.pdf
                parts = file_url.split('/documents/')
                if len(parts) > 1:
                    # Remove query params if any
                    file_path = parts[1].split('?')[0]
                    if supabase_storage.client:
                        storage = supabase_storage.client.storage.from_('documents')
                        storage.remove([file_path])
                        self.stdout.write(f"Deleted private bucket file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete Supabase file {file_url}: {str(e)}")
        else:
            # Local media file delete
            import os
            from django.conf import settings
            try:
                relative_path = file_url.replace(settings.MEDIA_URL, '')
                abs_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                if os.path.exists(abs_path):
                    os.remove(abs_path)
                    self.stdout.write(f"Deleted local file: {abs_path}")
            except Exception as e:
                logger.error(f"Failed to delete local file {file_url}: {str(e)}")
