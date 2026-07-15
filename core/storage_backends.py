import os
import uuid
import logging
from django.conf import settings
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseStorage:
    def __init__(self):
        self.supabase_url = getattr(settings, 'SUPABASE_URL', None)
        self.service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', None)
        self._client = None
        self._ensured_buckets: set = set()

    @property
    def client(self) -> Client:
        if self._client is None and self.supabase_url and self.service_role_key:
            self._client = create_client(self.supabase_url, self.service_role_key)
        return self._client

    def _ensure_bucket(self, bucket_name: str, public: bool = True):
        """Create the storage bucket if it doesn't already exist."""
        if bucket_name in self._ensured_buckets:
            return
        if not self.client:
            return
        try:
            self.client.storage.get_bucket(bucket_name)
        except Exception:
            try:
                self.client.storage.create_bucket(
                    bucket_name,
                    options={"public": public}
                )
                logger.info("Created Supabase bucket: %s", bucket_name)
            except Exception as e:
                # Bucket may already exist (race condition) — that's fine
                logger.debug("Bucket create returned: %s", e)
        self._ensured_buckets.add(bucket_name)

    def _do_upload(self, bucket_name: str, file_path: str, file_content: bytes, content_type: str) -> str:
        """
        Upload bytes to Supabase Storage and return the public URL.
        Handles supabase-py v2+ API changes gracefully.
        """
        storage = self.client.storage.from_(bucket_name)

        # supabase-py v2+ uses 'file' kwarg; older versions used 'data'.
        # Try the modern signature first, fall back to the legacy one.
        try:
            storage.upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": content_type}
            )
        except TypeError:
            # Fallback for older supabase-py that uses 'data' parameter
            storage.upload(
                path=file_path,
                data=file_content,
                file_options={"content-type": content_type}
            )

        # We already know the path we uploaded to — construct URL directly.
        # This is more reliable than parsing the upload response object,
        # which varies across supabase-py versions.
        public_url = storage.get_public_url(file_path)
        return public_url

    def upload_image(self, file, bucket_name: str = 'images', folder: str = '') -> str:
        if not self.client:
            raise Exception("Supabase client not configured. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

        file_ext = os.path.splitext(file.name)[1].lower()
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

        if file_ext not in allowed_extensions:
            raise Exception(f"Unsupported file type: {file_ext}")

        file_content = file.read()
        file_size = len(file_content)
        max_size = getattr(settings, 'MAX_FILE_SIZE', 5 * 1024 * 1024)

        if file_size > max_size:
            raise Exception(f"File too large. Max size: {max_size} bytes")

        file_name = f"{uuid.uuid4().hex}{file_ext}"
        file_path = f"{folder}/{file_name}" if folder else file_name

        self._ensure_bucket(bucket_name)

        try:
            return self._do_upload(bucket_name, file_path, file_content, self._get_content_type(file_ext))
        except Exception as e:
            logger.exception("Image upload failed for %s", file.name)
            raise Exception(f"Image upload failed: {e}")

    def upload_document(self, file, bucket_name: str = 'documents', folder: str = '') -> str:
        if not self.client:
            raise Exception("Supabase client not configured. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

        file_ext = os.path.splitext(file.name)[1].lower()
        allowed_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv',
            '.jpg', '.jpeg', '.png', '.webp', '.gif'
        }

        if file_ext not in allowed_extensions:
            raise Exception(f"Unsupported file type: {file_ext}")

        file_content = file.read()
        file_size = len(file_content)
        max_size = getattr(settings, 'MAX_FILE_SIZE', 5 * 1024 * 1024)

        if file_size > max_size:
            raise Exception(f"File too large. Max size: {max_size} bytes")

        file_name = f"{uuid.uuid4().hex}{file_ext}"
        file_path = f"{folder}/{file_name}" if folder else file_name

        self._ensure_bucket(bucket_name)

        try:
            return self._do_upload(bucket_name, file_path, file_content, self._get_content_type(file_ext))
        except Exception as e:
            logger.exception("Document upload failed for %s", file.name)
            raise Exception(f"Document upload failed: {e}")

    def delete_image(self, file_path: str, bucket_name: str = 'images') -> bool:
        if not self.client:
            raise Exception("Supabase client not configured.")

        try:
            self.client.storage.from_(bucket_name).remove([file_path])
            return True
        except Exception as e:
            logger.warning("Delete failed for %s: %s", file_path, e)
            return False

    def delete_file_from_url(self, url: str, bucket_name: str) -> bool:
        if not url:
            return False
        marker = f"/object/public/{bucket_name}/"
        if marker in url:
            file_path = url.split(marker)[-1]
            file_path = file_path.split('?')[0].split('#')[0]
            return self.delete_image(file_path, bucket_name)
        return False

    def _get_content_type(self, ext: str) -> str:
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.csv': 'text/csv',
        }
        return content_types.get(ext, 'application/octet-stream')

    def create_signed_url(self, file_path: str, bucket_name: str = 'documents', expires_in: int = 3600) -> str:
        if not self.client:
            return ""
        try:
            # Create private bucket if not ensured
            self._ensure_bucket(bucket_name, public=False)
            res = self.client.storage.from_(bucket_name).create_signed_url(file_path, expires_in)
            if isinstance(res, dict):
                return res.get('signedURL', res.get('signed_url', ''))
            return getattr(res, 'signed_url', str(res))
        except Exception as e:
            logger.error("Failed to create signed URL for path %s: %s", file_path, e)
            return ""


supabase_storage = SupabaseStorage()