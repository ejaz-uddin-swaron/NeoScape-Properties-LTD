from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from bookings_app.services.document_extractor import _normalize_ocr_text
from bookings_app.serializers import RentScheduleSerializer
from core.storage_backends import SupabaseStorage


class VerificationTests(SimpleTestCase):
    def test_issue_4_ocr_text_normalizer_numeric_scoping(self):
        """Fix verification #4: 0 <-> O replacement must be numeric-scoped."""
        # Non-numeric text must NOT change 'O' to '0'
        text_word = "October Room"
        self.assertEqual(_normalize_ocr_text(text_word), "October Room")

        # Numeric context with 'O' instead of '0' should normalize to '0'
        text_numeric = "Room 1O1 Score 7O0"
        self.assertEqual(_normalize_ocr_text(text_numeric), "Room 101 Score 700")

    def test_issue_5_magic_byte_validation(self):
        """Fix verification #5: Disguised binary/executable payload must raise error."""
        storage = SupabaseStorage()
        
        # Fake exe file content disguised as .jpg
        fake_jpg_exe = SimpleUploadedFile("malicious.jpg", b"MZexecutable_bytes_here", content_type="image/jpeg")
        with self.assertRaisesMessage(Exception, "Security violation: Executable or binary payload detected."):
            storage._validate_file_magic_bytes(fake_jpg_exe.read(), ".jpg")

        # Valid JPEG header
        valid_jpg = SimpleUploadedFile("valid.jpg", b"\xff\xd8\xff\xe0valid_jpeg", content_type="image/jpeg")
        # Should pass without exception (no error raised)
        storage._validate_file_magic_bytes(valid_jpg.read(), ".jpg")

    def test_issue_12_rent_schedule_serializer_has_room_id_field(self):
        """Fix verification #12: RentScheduleSerializer must expose room_id field."""
        serializer = RentScheduleSerializer()
        self.assertIn('room_id', serializer.fields, "room_id field must exist in RentScheduleSerializer")
