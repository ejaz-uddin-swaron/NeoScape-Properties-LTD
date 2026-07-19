from rest_framework import serializers
from .models import Booking, RentSchedule, RentPayment, TenantAssignment, ChatChannel, ChatMessage, TenancyAgreement, ReferencingApplication


class BookingSerializer(serializers.ModelSerializer):
    roomId = serializers.CharField(source='room.id', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'roomId', 'check_in', 'check_out', 'guests', 'total_price', 'status', 'guest_info',
            'created_at', 'updated_at'
        ]


class RentPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentPayment
        fields = [
            'id', 'due_date', 'paid_date', 'amount', 'paid_amount', 'status',
            'payment_method', 'notes', 'created_at'
        ]


class RentScheduleSerializer(serializers.ModelSerializer):
    payment_history = RentPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = RentSchedule
        fields = [
            'id', 'room_name', 'tenant_name', 'tenant_email', 'tenant_phone',
            'monthly_rent', 'due_day', 'start_date', 'end_date', 'status',
            'tenant_user', 'assignment',
            'payment_history', 'created_at', 'updated_at'
        ]


class RentScheduleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentSchedule
        fields = [
            'room_name', 'tenant_name', 'tenant_email', 'tenant_phone',
            'monthly_rent', 'due_day', 'start_date', 'end_date',
            'tenant_user', 'assignment'
        ]


class RentPaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentPayment
        fields = ['due_date', 'paid_date', 'amount', 'paid_amount', 'status', 'payment_method', 'notes']


class TenantAssignmentSerializer(serializers.ModelSerializer):
    tenantId = serializers.IntegerField(source='tenant.id', read_only=True)
    tenantUsername = serializers.CharField(source='tenant.username', read_only=True)
    tenantEmail = serializers.CharField(source='tenant.email', read_only=True)
    roomId = serializers.IntegerField(source='room.id', read_only=True)
    roomName = serializers.CharField(source='room.name', read_only=True)
    roomLocation = serializers.CharField(source='room.location', read_only=True)

    class Meta:
        model = TenantAssignment
        fields = [
            'id', 'tenantId', 'tenantUsername', 'tenantEmail',
            'roomId', 'roomName', 'roomLocation',
            'property_name', 'start_date', 'end_date', 'status',
            'monthly_rent', 'deposit', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TenantAssignmentCreateSerializer(serializers.ModelSerializer):
    tenant_id = serializers.IntegerField(write_only=True)
    room_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = TenantAssignment
        fields = [
            'tenant_id', 'room_id', 'property_name',
            'start_date', 'end_date', 'status',
            'monthly_rent', 'deposit', 'notes'
        ]

    def create(self, validated_data):
        from django.contrib.auth.models import User
        from rooms.models import Room
        from .models import RentSchedule

        tenant_id = validated_data.pop('tenant_id')
        room_id = validated_data.pop('room_id')

        try:
            tenant = User.objects.get(id=tenant_id)
        except User.DoesNotExist:
            raise serializers.ValidationError({'tenant_id': 'User not found'})

        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            raise serializers.ValidationError({'room_id': 'Room not found'})

        # Auto-fill property_name from room location if not provided
        if not validated_data.get('property_name'):
            validated_data['property_name'] = room.location

        assignment = TenantAssignment.objects.create(
            tenant=tenant,
            room=room,
            **validated_data
        )

        # Create a matching rent schedule so tenant views populate immediately.
        tenant_client = getattr(tenant, 'client', None)
        tenant_phone = getattr(tenant_client, 'mobile_no', '') if tenant_client else ''
        RentSchedule.objects.create(
            room_name=room.name,
            tenant_name=tenant.get_full_name() or tenant.username,
            tenant_email=tenant.email or '',
            tenant_phone=tenant_phone or '',
            monthly_rent=assignment.monthly_rent,
            due_day=1,
            start_date=assignment.start_date,
            end_date=assignment.end_date,
            status='active' if assignment.status == 'active' else assignment.status,
            tenant_user=tenant,
            assignment=assignment,
        )

        return assignment


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.SerializerMethodField()
    sender_role = serializers.SerializerMethodField()

    def get_sender_username(self, obj):
        name = f"{obj.sender.first_name} {obj.sender.last_name}".strip()
        if name:
            return name
        return obj.sender.email or obj.sender.username

    class Meta:
        model = ChatMessage
        fields = ['id', 'channel', 'sender', 'sender_username', 'sender_role', 'content', 'file_url', 'file_name', 'extracted_text', 'created_at']
        read_only_fields = ['id', 'channel', 'sender', 'created_at']


    def get_sender_role(self, obj):
        client = getattr(obj.sender, 'client', None)
        return getattr(client, 'role', 'customer') if client else 'customer'


class ChatChannelSerializer(serializers.ModelSerializer):
    tenant_username = serializers.CharField(source='tenant.username', read_only=True)
    admin_username = serializers.CharField(source='admin.username', read_only=True, allow_null=True)
    latest_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatChannel
        fields = ['id', 'property_name', 'tenant', 'tenant_username', 'admin', 'admin_username', 'created_at', 'latest_message']
        read_only_fields = ['id', 'created_at']

    def get_latest_message(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        if msg:
            return {
                'id': msg.id,
                'content': msg.content,
                'sender_username': msg.sender.username,
                'created_at': msg.created_at.isoformat(),
                'file_url': msg.file_url,
                'file_name': msg.file_name,
            }
        return None


class TenancyAgreementSerializer(serializers.ModelSerializer):
    tenant_username = serializers.CharField(source='tenant.username', read_only=True)
    tenant_full_name = serializers.SerializerMethodField()
    signature_summary = serializers.SerializerMethodField()

    class Meta:
        model = TenancyAgreement
        fields = [
            'id', 'channel', 'property_name', 'tenant', 'tenant_username', 'tenant_full_name', 'room_id',
            'agreement_text', 'status',
            'tenant_signed', 'tenant_signature_svg', 'tenant_signed_at',
            'admin_signed', 'admin_signature_svg', 'admin_signed_at',
            'signature_summary',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_tenant_full_name(self, obj):
        name = f"{obj.tenant.first_name} {obj.tenant.last_name}".strip()
        return name if name else obj.tenant.email or obj.tenant.username

    def get_signature_summary(self, obj):
        return {
            'tenant_signed': obj.tenant_signed,
            'tenant_has_signature': bool(obj.tenant_signature_svg),
            'tenant_signed_at': obj.tenant_signed_at.isoformat() if obj.tenant_signed_at else None,
            'admin_signed': obj.admin_signed,
            'admin_has_signature': bool(obj.admin_signature_svg),
            'admin_signed_at': obj.admin_signed_at.isoformat() if obj.admin_signed_at else None,
            'fully_signed': obj.tenant_signed and obj.admin_signed,
        }


class ReferencingApplicationSerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source='property_room.name', read_only=True)
    property_location = serializers.CharField(source='property_room.location', read_only=True)
    landlord_username = serializers.CharField(source='landlord_user.username', read_only=True)
    landlord_full_name = serializers.SerializerMethodField()
    uploaded_documents = serializers.SerializerMethodField()
    decision_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = ReferencingApplication
        fields = [
            'id', 'token', 'property_room', 'property_name', 'property_location',
            'landlord_user', 'landlord_username', 'landlord_full_name',
            'applicant_name', 'applicant_email', 'applicant_phone',
            'application_data', 'uploaded_documents', 'credit_score', 'ccj_iva_found', 'missed_payments',
            'ai_raw_check_result', 'report_pdf_url', 'decision', 'decision_display',
            'landlord_override_notes',
            'tenancy_end_date', 'resolved_at', 'legal_dispute_active', 'is_archived_or_deleted',
            'status', 'status_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'token', 'created_at', 'updated_at']

    def get_landlord_full_name(self, obj):
        name = f"{obj.landlord_user.first_name} {obj.landlord_user.last_name}".strip()
        return name if name else obj.landlord_user.email or obj.landlord_user.username

    def get_decision_display(self, obj):
        return obj.get_decision_display()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_uploaded_documents(self, obj):
        from core.storage_backends import supabase_storage
        docs = obj.uploaded_documents
        resolved_docs = []
        for doc in docs:
            file_path = ""
            file_name = ""
            if isinstance(doc, dict):
                file_path = doc.get('file_path', doc.get('file_url', ''))
                file_name = doc.get('file_name', '')
            elif isinstance(doc, str):
                file_path = doc
                file_name = doc.split('/')[-1]

            if file_path.startswith("referencing/"):
                signed_url = supabase_storage.create_signed_url(file_path, bucket_name='documents', expires_in=3600)
                resolved_docs.append({
                    'file_url': signed_url,
                    'file_path': file_path,
                    'file_name': file_name
                })
            else:
                resolved_docs.append({
                    'file_url': file_path,
                    'file_path': file_path,
                    'file_name': file_name
                })
        return resolved_docs



