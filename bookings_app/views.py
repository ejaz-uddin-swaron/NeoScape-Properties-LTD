from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rooms.permissions import IsAdmin, IsTenant, IsAdminOrTenant
from rooms.models import Room
from .models import Booking, TenantAssignment, ChatChannel, ChatMessage, TenancyAgreement
from . import serializers



class BookingsView(APIView):
    """
    Admin-only booking management.
    GET: retrieve all bookings.
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = Booking.objects.select_related('room', 'user').all()
        data = []
        for b in qs:
            data.append({
                'id': b.id,
                'userId': b.user.id if b.user else None,
                'username': b.user.username if b.user else 'Guest',
                'roomId': str(b.room.id),
                'checkIn': b.check_in.isoformat(),
                'checkOut': b.check_out.isoformat(),
                'guests': b.guests,
                'totalPrice': float(b.total_price),
                'status': b.status,
                'guestInfo': b.guest_info,
                'createdAt': b.created_at.isoformat(),
                'updatedAt': b.updated_at.isoformat(),
                'room': {
                    'id': str(b.room.id),
                    'name': b.room.name,
                    'location': b.room.location,
                }
            })
        return Response({'success': True, 'data': data})


class UpdateBookingStatusView(APIView):
    """Admin-only booking status update."""
    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        status_val = request.data.get('status')
        if status_val not in ['pending', 'confirmed', 'cancelled', 'completed']:
            return Response({'success': False, 'error': 'Invalid status', 'status': 422}, status=422)

        try:
            b = Booking.objects.get(id=pk)
        except Booking.DoesNotExist:
            return Response({'success': False, 'error': 'Booking not found', 'status': 404}, status=404)

        b.status = status_val
        b.save(update_fields=['status', 'updated_at'])
        return Response({'success': True, 'data': {'id': b.id, 'status': b.status, 'updatedAt': b.updated_at.isoformat()}})


class RentScheduleView(APIView):
    """Admin-only rent schedule management."""
    permission_classes = [IsAdmin]

    def get(self, request):
        from .models import RentSchedule
        schedules = RentSchedule.objects.all().prefetch_related('payment_history')
        serializer = serializers.RentScheduleSerializer(schedules, many=True)
        return Response({'success': True, 'data': serializer.data})

    def post(self, request):
        from .models import RentSchedule
        serializer = serializers.RentScheduleCreateSerializer(data=request.data)
        if serializer.is_valid():
            schedule = serializer.save()
            return Response({'success': True, 'data': serializers.RentScheduleSerializer(schedule).data}, status=201)
        return Response({'success': False, 'error': serializer.errors}, status=400)


class RentScheduleDetailView(APIView):
    """Admin-only rent schedule detail, update, delete."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        from .models import RentSchedule
        try:
            schedule = RentSchedule.objects.prefetch_related('payment_history').get(pk=pk)
            return Response({'success': True, 'data': serializers.RentScheduleSerializer(schedule).data})
        except RentSchedule.DoesNotExist:
            return Response({'success': False, 'error': 'Schedule not found', 'status': 404}, status=404)

    def put(self, request, pk):
        from .models import RentSchedule
        try:
            schedule = RentSchedule.objects.get(pk=pk)
            serializer = serializers.RentScheduleSerializer(schedule, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({'success': True, 'data': serializer.data})
            return Response({'success': False, 'error': serializer.errors}, status=400)
        except RentSchedule.DoesNotExist:
            return Response({'success': False, 'error': 'Schedule not found', 'status': 404}, status=404)

    def delete(self, request, pk):
        from .models import RentSchedule
        try:
            schedule = RentSchedule.objects.get(pk=pk)
            schedule.delete()
            return Response({'success': True, 'message': 'Schedule deleted'})
        except RentSchedule.DoesNotExist:
            return Response({'success': False, 'error': 'Schedule not found', 'status': 404}, status=404)


class RentPaymentView(APIView):
    """Admin-only rent payment recording."""
    permission_classes = [IsAdmin]

    def post(self, request, schedule_id):
        from .models import RentSchedule, RentPayment
        try:
            schedule = RentSchedule.objects.get(pk=schedule_id)
        except RentSchedule.DoesNotExist:
            return Response({'success': False, 'error': 'Schedule not found', 'status': 404}, status=404)

        serializer = serializers.RentPaymentCreateSerializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save(schedule=schedule)
            return Response({'success': True, 'data': serializers.RentPaymentSerializer(payment).data}, status=201)
        return Response({'success': False, 'error': serializer.errors}, status=400)


class RentReminderView(APIView):
    """Admin-only rent due reminders."""
    permission_classes = [IsAdmin]

    def get(self, request):
        from .models import RentSchedule
        today = timezone.now().date()
        reminders = []

        schedules = RentSchedule.objects.all().prefetch_related('payment_history')
        for schedule in schedules:
            if schedule.status != 'active':
                continue

            last_day = (timezone.datetime(today.year, today.month, 28) + timezone.timedelta(days=4)).replace(day=1) - timezone.timedelta(days=1)
            safe_due_day = min(schedule.due_day, last_day.day)
            due_date = timezone.datetime(today.year, today.month, safe_due_day).date()
            days_until_due = (due_date - today).days

            if days_until_due <= 5 and days_until_due >= -30:
                current_month = today.strftime('%Y-%m')
                payment_exists = any(
                    p.due_date.strftime('%Y-%m') == current_month and p.status == 'paid'
                    for p in schedule.payment_history.all()
                )
                if not payment_exists:
                    reminders.append({
                        'id': f"rent-{schedule.id}-{current_month}",
                        'scheduleId': schedule.id,
                        'roomName': schedule.room_name,
                        'tenantName': schedule.tenant_name,
                        'dueDate': due_date.isoformat(),
                        'amount': float(schedule.monthly_rent),
                        'dismissed': False,
                    })

        return Response({'success': True, 'data': reminders})


# ─── Tenant Assignment Views ──────────────────────────────────────────────────


class TenantAssignmentListView(APIView):
    """Admin: list and create tenant-room assignments."""
    permission_classes = [IsAdmin]

    def get(self, request):
        status_filter = request.query_params.get('status')
        qs = TenantAssignment.objects.select_related('tenant', 'room').all()
        if status_filter:
            qs = qs.filter(status=status_filter)
        serializer = serializers.TenantAssignmentSerializer(qs, many=True)
        return Response({'success': True, 'data': serializer.data})

    def post(self, request):
        serializer = serializers.TenantAssignmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            assignment = serializer.save()
            # Auto-promote user to tenant role if they're still a customer
            try:
                from accounts.models import Client
                client, _ = Client.objects.get_or_create(
                    user=assignment.tenant,
                    defaults={'mobile_no': '', 'role': 'tenant', 'image': ''}
                )
                if client.role == 'customer':
                    client.role = 'tenant'
                    client.save(update_fields=['role'])
            except Exception:
                pass

            return Response({
                'success': True,
                'data': serializers.TenantAssignmentSerializer(assignment).data
            }, status=201)
        return Response({'success': False, 'error': serializer.errors}, status=400)


class TenantAssignmentDetailView(APIView):
    """Admin: update and delete tenant assignments."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        try:
            assignment = TenantAssignment.objects.select_related('tenant', 'room').get(pk=pk)
            return Response({'success': True, 'data': serializers.TenantAssignmentSerializer(assignment).data})
        except TenantAssignment.DoesNotExist:
            return Response({'success': False, 'error': 'Assignment not found'}, status=404)

    def put(self, request, pk):
        try:
            assignment = TenantAssignment.objects.get(pk=pk)
            serializer = serializers.TenantAssignmentSerializer(assignment, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({'success': True, 'data': serializer.data})
            return Response({'success': False, 'error': serializer.errors}, status=400)
        except TenantAssignment.DoesNotExist:
            return Response({'success': False, 'error': 'Assignment not found'}, status=404)

    def delete(self, request, pk):
        try:
            assignment = TenantAssignment.objects.get(pk=pk)
            assignment.delete()
            return Response({'success': True, 'message': 'Assignment deleted'})
        except TenantAssignment.DoesNotExist:
            return Response({'success': False, 'error': 'Assignment not found'}, status=404)


class MyAssignmentView(APIView):
    """Tenant: view own assignment (property, room, rent details)."""
    permission_classes = [IsAdminOrTenant]

    def get(self, request):
        assignments = TenantAssignment.objects.select_related('tenant', 'room').filter(
            tenant=request.user,
            status='active'
        )
        if not assignments.exists():
            return Response({'success': True, 'data': None, 'message': 'No active assignment found'})

        serializer = serializers.TenantAssignmentSerializer(assignments.first())
        # Also include room details
        assignment = assignments.first()
        from rooms.serializers import RoomSerializer
        room_data = RoomSerializer(assignment.room).data

        return Response({
            'success': True,
            'data': {
                'assignment': serializer.data,
                'room': room_data,
            }
        })


# ─── Tenant Rent Views ────────────────────────────────────────────────────────


def _auto_generate_payments(schedule):
    """
    Auto-generate pending RentPayment records for each month
    from the schedule's start_date up to the current month.
    Skips months that already have a payment record.
    Marks past-due payments as 'overdue'.
    """
    from .models import RentPayment
    from datetime import date
    import calendar

    today = timezone.now().date()
    start = schedule.start_date

    # Don't generate for non-active schedules
    if schedule.status != 'active':
        return

    # Walk month-by-month from start_date to the current month
    year, month = start.year, start.month
    while date(year, month, 1) <= today.replace(day=1):
        # Clamp due_day to the last day of the month
        last_day = calendar.monthrange(year, month)[1]
        due_day = min(schedule.due_day, last_day)
        due_date = date(year, month, due_day)

        # Only generate if no payment exists for this month yet
        exists = RentPayment.objects.filter(
            schedule=schedule,
            due_date__year=year,
            due_date__month=month
        ).exists()

        if not exists:
            payment_status = 'overdue' if due_date < today else 'pending'
            RentPayment.objects.create(
                schedule=schedule,
                due_date=due_date,
                amount=schedule.monthly_rent,
                status=payment_status,
            )

        # Advance to next month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1


class MyRentSchedulesView(APIView):
    """Tenant: view own rent schedules."""
    permission_classes = [IsAdminOrTenant]

    def get(self, request):
        from .models import RentSchedule
        # Find schedules linked to this user directly, or by matching tenant name/email
        schedules = RentSchedule.objects.filter(
            tenant_user=request.user
        ).prefetch_related('payment_history')

        # Fallback: also match by email if no direct FK link
        if not schedules.exists():
            schedules = RentSchedule.objects.filter(
                tenant_email=request.user.email
            ).prefetch_related('payment_history')

        # Auto-generate any missing monthly payment records
        for schedule in schedules:
            _auto_generate_payments(schedule)

        # Re-fetch with fresh payment_history after generation
        schedules = schedules.all()

        serializer = serializers.RentScheduleSerializer(schedules, many=True)
        return Response({'success': True, 'data': serializer.data})


class MyRentRemindersView(APIView):
    """Tenant: view own upcoming rent reminders."""
    permission_classes = [IsAdminOrTenant]

    def get(self, request):
        from .models import RentSchedule
        today = timezone.now().date()
        reminders = []

        # Get schedules for this tenant
        schedules = RentSchedule.objects.filter(
            tenant_user=request.user
        ).prefetch_related('payment_history')

        if not schedules.exists():
            schedules = RentSchedule.objects.filter(
                tenant_email=request.user.email
            ).prefetch_related('payment_history')

        for schedule in schedules:
            if schedule.status != 'active':
                continue

            last_day = (timezone.datetime(today.year, today.month, 28) + timezone.timedelta(days=4)).replace(day=1) - timezone.timedelta(days=1)
            safe_due_day = min(schedule.due_day, last_day.day)
            due_date = timezone.datetime(today.year, today.month, safe_due_day).date()
            days_until_due = (due_date - today).days

            if days_until_due <= 14 and days_until_due >= -30:
                current_month = today.strftime('%Y-%m')
                payment_exists = any(
                    p.due_date.strftime('%Y-%m') == current_month and p.status == 'paid'
                    for p in schedule.payment_history.all()
                )
                if not payment_exists:
                    reminders.append({
                        'id': f"rent-{schedule.id}-{current_month}",
                        'scheduleId': schedule.id,
                        'roomName': schedule.room_name,
                        'dueDate': due_date.isoformat(),
                        'amount': float(schedule.monthly_rent),
                        'daysUntilDue': days_until_due,
                        'isOverdue': days_until_due < 0,
                    })

        return Response({'success': True, 'data': reminders})


# ─── Chat Channels & Messages API ───────────────────────────────────────────

class ChatChannelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        client = getattr(user, 'client', None)
        role = getattr(client, 'role', 'customer') if client else 'customer'
        
        if role == 'admin' or user.is_staff:
            channels = ChatChannel.objects.select_related('tenant', 'admin').all().prefetch_related('messages')
            serializer = serializers.ChatChannelSerializer(channels, many=True)
            return Response({'success': True, 'data': serializer.data})
        else:
            # Tenant
            # Find active assignment to know the property name
            assignment = TenantAssignment.objects.filter(tenant=user, status='active').first()
            prop_name = assignment.property_name if assignment else "General Inquiry"
            
            # Get or create channel for this tenant
            channel, created = ChatChannel.objects.get_or_create(
                tenant=user,
                defaults={'property_name': prop_name}
            )
            # Update property name if it changed/was initialized
            if not created and assignment and channel.property_name != assignment.property_name:
                channel.property_name = assignment.property_name
                channel.save()
                
            serializer = serializers.ChatChannelSerializer(channel)
            return Response({'success': True, 'data': serializer.data})

    def post(self, request):
        user = request.user
        client = getattr(user, 'client', None)
        role = getattr(client, 'role', 'customer') if client else 'customer'
        
        if role == 'admin' or user.is_staff:
            tenant_id = request.data.get('tenant_id')
            property_name = request.data.get('property_name')
            
            if not tenant_id or not property_name:
                return Response({'success': False, 'error': 'tenant_id and property_name are required'}, status=400)
                
            from django.contrib.auth.models import User
            try:
                tenant_user = User.objects.get(id=tenant_id)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'Tenant user not found'}, status=404)
                
            channel, created = ChatChannel.objects.get_or_create(
                tenant=tenant_user,
                defaults={'property_name': property_name, 'admin': user}
            )
            serializer = serializers.ChatChannelSerializer(channel)
            return Response({'success': True, 'data': serializer.data}, status=201 if created else 200)
        else:
            return Response({'success': False, 'error': 'Permission denied'}, status=403)



class ChatMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_id):
        try:
            channel = ChatChannel.objects.get(id=channel_id)
        except ChatChannel.DoesNotExist:
            return Response({'success': False, 'error': 'Channel not found'}, status=404)
        
        # Verify permissions: only admin or the channel's tenant can read
        user = request.user
        client = getattr(user, 'client', None)
        role = getattr(client, 'role', 'customer') if client else 'customer'
        if role != 'admin' and not user.is_staff and channel.tenant != user:
            return Response({'success': False, 'error': 'Permission denied'}, status=403)
            
        messages = channel.messages.all().order_by('created_at')
        serializer = serializers.ChatMessageSerializer(messages, many=True)
        return Response({'success': True, 'data': serializer.data})

    def post(self, request, channel_id):
        try:
            channel = ChatChannel.objects.get(id=channel_id)
        except ChatChannel.DoesNotExist:
            return Response({'success': False, 'error': 'Channel not found'}, status=404)
            
        user = request.user
        client = getattr(user, 'client', None)
        role = getattr(client, 'role', 'customer') if client else 'customer'
        if role != 'admin' and not user.is_staff and channel.tenant != user:
            return Response({'success': False, 'error': 'Permission denied'}, status=403)
            
        serializer = serializers.ChatMessageSerializer(data=request.data)
        if serializer.is_valid():
            msg = serializer.save(channel=channel, sender=user)
            
            # Extract text if file uploaded
            if msg.file_url:
                try:
                    from bookings_app.services.document_extractor import extract_text_from_url
                    msg.extracted_text = extract_text_from_url(msg.file_url, msg.file_name)
                    msg.save(update_fields=['extracted_text'])
                except Exception as e:
                    # Log but don't fail message creation
                    print(f"Extraction failed: {str(e)}")
                
                # Copy file to tenant documents if sent by an admin
                if role == 'admin' or user.is_staff:
                    try:
                        from rooms.models import PropertyDocument
                        PropertyDocument.objects.create(
                            property_id=channel.property_name,
                            tenant=channel.tenant,
                            uploaded_by=user,
                            name=msg.file_name or "Chat Attachment",
                            file_url=msg.file_url,
                            type='other',
                            status='approved',
                            admin_notes="Uploaded via Admin Chat"
                        )
                    except Exception as e:
                        print(f"Failed to save document to tenant profile: {str(e)}")
                    
            return Response({'success': True, 'data': serializers.ChatMessageSerializer(msg).data}, status=201)
        return Response({'success': False, 'error': serializer.errors}, status=400)


# ─── AI Tenancy Agreement Draft Generator ─────────────────────────────────────

class GenerateAgreementView(APIView):
    permission_classes = [IsAdmin] # Only admins generate drafts

    def post(self, request):
        channel_id = request.data.get('channel_id')
        if not channel_id:
            return Response({'success': False, 'error': 'channel_id is required'}, status=400)
            
        try:
            channel = ChatChannel.objects.get(id=channel_id)
        except ChatChannel.DoesNotExist:
            return Response({'success': False, 'error': 'Channel not found'}, status=404)
            
        # Get active assignment for the tenant to gather baseline contract info
        tenant = channel.tenant
        assignment = TenantAssignment.objects.filter(tenant=tenant, status='active').first()
        
        # Build context from assignment
        tenant_identifier = f"{tenant.first_name} {tenant.last_name}".strip() or tenant.email or tenant.username
        details_context = f"Tenant: {tenant_identifier}\nTenant Email: {tenant.email}\n"
        if assignment:
            details_context += f"Property Name: {assignment.property_name}\n"
            details_context += f"Room: {assignment.room.name if assignment.room else 'N/A'}\n"
            details_context += f"Monthly Rent: £{assignment.monthly_rent}\n"
            details_context += f"Security Deposit: £{assignment.deposit}\n"
            details_context += f"Start Date: {assignment.start_date}\n"
            if assignment.end_date:
                details_context += f"End Date: {assignment.end_date}\n"
        else:
            details_context += f"Property Name: {channel.property_name}\n"
            
        # Compile Chat History
        chat_messages = channel.messages.all().order_by('created_at')
        chat_log = ""
        extracted_documents_content = ""
        
        for msg in chat_messages:
            sender_label = "Admin" if msg.sender.is_staff or (hasattr(msg.sender, 'client') and msg.sender.client.role == 'admin') else "Tenant"
            sender_identifier = f"{msg.sender.first_name} {msg.sender.last_name}".strip() or msg.sender.email or msg.sender.username
            chat_log += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {sender_label} ({sender_identifier}): {msg.content}\n"
            
            if msg.file_url and msg.extracted_text:
                extracted_documents_content += f"--- Document Shared: {msg.file_name or 'unnamed'} ---\n{msg.extracted_text}\n\n"
                
        # Call Groq API
        from openai import OpenAI
        from django.conf import settings
        
        api_key = getattr(settings, 'NEOSCAPE_API_KEY', '')
        if not api_key:
            return Response({'success': False, 'error': 'Groq/NeoScape API Key is not configured on the backend settings.'}, status=500)
            
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            
            SYSTEM_PROMPT = """You are a professional real estate legal assistant. 
Your job is to generate a comprehensive Tenancy Agreement in Markdown format.
Use the provided Chat History (negotiations), System Records (assignment details), and Extracted Terms/Inventory Files.
Ensure you cover:
1. Names of parties (Landlord/Tenant).
2. Property Address and Room details.
3. Rental terms (amount, due date, deposit).
4. Rules, terms and conditions.
5. Inventory list of items and their condition (based on the chat and uploaded files).
Return only the Markdown agreement ready to sign. Do not include introductory notes, chat banter, or explanation. Begin directly with the contract title (e.g. # RESIDENTIAL TENANCY AGREEMENT)."""

            USER_PROMPT = f"""System Records (Baseline Details):
{details_context}

Chat History:
{chat_log}

Extracted Document Texts (shared terms/inventories):
{extracted_documents_content}
"""

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT}
                ],
                temperature=0.2,
            )
            
            agreement_text = response.choices[0].message.content
            
            # Create or update draft agreement in database
            agreement, created = TenancyAgreement.objects.get_or_create(
                channel=channel,
                defaults={
                    'property_name': channel.property_name,
                    'tenant': tenant,
                    'room_id': assignment.room.id if assignment and assignment.room else None,
                    'agreement_text': agreement_text,
                    'status': 'draft'
                }
            )
            if not created:
                agreement.agreement_text = agreement_text
                # Reset signatures since we regenerated the draft
                agreement.tenant_signed = False
                agreement.tenant_signature_svg = None
                agreement.tenant_signed_at = None
                agreement.admin_signed = False
                agreement.admin_signature_svg = None
                agreement.admin_signed_at = None
                agreement.status = 'draft'
                agreement.save()
                
            return Response({
                'success': True,
                'data': serializers.TenancyAgreementSerializer(agreement).data
            })
            
        except Exception as e:
            return Response({'success': False, 'error': f"AI Agreement generation failed: {str(e)}"}, status=500)


# ─── Tenancy Agreement Signatures & Review API ─────────────────────────────────

class TenancyAgreementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        channel_id = request.query_params.get('channel_id')
        user = request.user
        client = getattr(user, 'client', None)
        role = getattr(client, 'role', 'customer') if client else 'customer'
        
        if channel_id:
            try:
                channel = ChatChannel.objects.get(id=channel_id)
            except ChatChannel.DoesNotExist:
                return Response({'success': False, 'error': 'Channel not found'}, status=404)
                
            if role != 'admin' and not user.is_staff and channel.tenant != user:
                return Response({'success': False, 'error': 'Permission denied'}, status=403)
                
            agreements = TenancyAgreement.objects.filter(channel=channel)
        else:
            if role == 'admin' or user.is_staff:
                agreements = TenancyAgreement.objects.all()
            else:
                agreements = TenancyAgreement.objects.filter(tenant=user)
                
        serializer = serializers.TenancyAgreementSerializer(agreements, many=True)
        return Response({'success': True, 'data': serializer.data})


class TenancyAgreementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return TenancyAgreement.objects.get(pk=pk)
        except TenancyAgreement.DoesNotExist:
            return None

    def get(self, request, pk):
        agreement = self.get_object(pk)
        if not agreement:
            return Response({'success': False, 'error': 'Agreement not found'}, status=404)
            
        user = request.user
        client = getattr(user, 'client', None)
        role = getattr(client, 'role', 'customer') if client else 'customer'
        if role != 'admin' and not user.is_staff and agreement.tenant != user:
            return Response({'success': False, 'error': 'Permission denied'}, status=403)
            
        return Response({'success': True, 'data': serializers.TenancyAgreementSerializer(agreement).data})

    def patch(self, request, pk):
        agreement = self.get_object(pk)
        if not agreement:
            return Response({'success': False, 'error': 'Agreement not found'}, status=404)
            
        user = request.user
        client = getattr(user, 'client', None)
        role = getattr(client, 'role', 'customer') if client else 'customer'
        
        status_val = request.data.get('status')
        text_val = request.data.get('agreement_text')
        
        if status_val == 'rejected':
            agreement.status = 'rejected'
            agreement.save(update_fields=['status'])
            return Response({'success': True, 'data': serializers.TenancyAgreementSerializer(agreement).data})
            
        if role == 'admin' or user.is_staff:
            if text_val:
                agreement.agreement_text = text_val
            if status_val:
                agreement.status = status_val
            agreement.save()
            return Response({'success': True, 'data': serializers.TenancyAgreementSerializer(agreement).data})
        else:
            return Response({'success': False, 'error': 'Permission denied'}, status=403)


class SignAgreementView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            agreement = TenancyAgreement.objects.get(pk=pk)
        except TenancyAgreement.DoesNotExist:
            return Response({'success': False, 'error': 'Agreement not found'}, status=404)
            
        user = request.user
        client = getattr(user, 'client', None)
        role = getattr(client, 'role', 'customer') if client else 'customer'
        
        signature_svg = request.data.get('signature_svg')
        if not signature_svg:
            return Response({'success': False, 'error': 'signature_svg is required'}, status=400)
            
        if role == 'admin' or user.is_staff:
            agreement.admin_signed = True
            agreement.admin_signature_svg = signature_svg
            agreement.admin_signed_at = timezone.now()
        elif agreement.tenant == user:
            agreement.tenant_signed = True
            agreement.tenant_signature_svg = signature_svg
            agreement.tenant_signed_at = timezone.now()
        else:
            return Response({'success': False, 'error': 'You are not authorized to sign this agreement.'}, status=403)
            
        if agreement.tenant_signed and agreement.admin_signed:
            agreement.status = 'signed'
            
        agreement.save()
        return Response({
            'success': True,
            'data': serializers.TenancyAgreementSerializer(agreement).data
        })


import secrets
from django.core.mail import send_mail
from django.conf import settings
from .models import ReferencingApplication

class ReferencingApplicationListCreateView(APIView):
    """
    Landlord views for managing Tenant Referencing invites and submissions.
    """
    permission_classes = [IsAuthenticated] # Assume any authenticated user is staff/landlord for now

    def get(self, request):
        applications = ReferencingApplication.objects.filter(is_archived_or_deleted=False).order_by('-created_at')
        serializer = serializers.ReferencingApplicationSerializer(applications, many=True)
        return Response({'success': True, 'data': serializer.data})

    def post(self, request):
        property_room_id = request.data.get('room_id')
        applicant_name = request.data.get('applicant_name')
        applicant_email = request.data.get('applicant_email')
        applicant_phone = request.data.get('applicant_phone', '')

        if not all([property_room_id, applicant_name, applicant_email]):
            return Response({'success': False, 'error': 'room_id, applicant_name, and applicant_email are required'}, status=400)

        try:
            room = Room.objects.get(pk=property_room_id)
        except Room.DoesNotExist:
            return Response({'success': False, 'error': 'Room not found'}, status=404)

        token = secrets.token_urlsafe(32)
        app = ReferencingApplication.objects.create(
            token=token,
            property_room=room,
            landlord_user=request.user,
            applicant_name=applicant_name,
            applicant_email=applicant_email,
            applicant_phone=applicant_phone,
            status='invited'
        )

        # Send invite email
        # Public invitation link
        frontend_base = getattr(settings, 'FRONTEND_URL', 'https://neoscapeproperties.co.uk').rstrip('/')
        invite_link = f"{frontend_base}/referencing/{token}"
        subject = f"Tenant Referencing Invitation for {room.name}"
        body = (
            f"Dear {applicant_name},\n\n"
            f"You have been invited by {request.user.username} to undergo tenant referencing for the property: {room.name} ({room.location}).\n\n"
            f"Please complete your referencing application at the following link:\n"
            f"{invite_link}\n\n"
            f"Thank you,\nNeoScape Properties Management"
        )
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL or 'noreply@neoscapeproperties.com',
                [applicant_email],
                fail_silently=True
            )
        except Exception as e:
            # log or handle email error silently
            pass

        return Response({
            'success': True,
            'data': serializers.ReferencingApplicationSerializer(app).data
        })


class ReferencingApplicationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            app = ReferencingApplication.objects.get(pk=pk, is_archived_or_deleted=False)
        except ReferencingApplication.DoesNotExist:
            return Response({'success': False, 'error': 'Application not found'}, status=404)
        return Response({'success': True, 'data': serializers.ReferencingApplicationSerializer(app).data})

    def patch(self, request, pk):
        try:
            app = ReferencingApplication.objects.get(pk=pk, is_archived_or_deleted=False)
        except ReferencingApplication.DoesNotExist:
            return Response({'success': False, 'error': 'Application not found'}, status=404)

        decision = request.data.get('decision')
        landlord_notes = request.data.get('landlord_override_notes')
        status_val = request.data.get('status')

        if decision:
            if decision not in dict(ReferencingApplication.DECISION_CHOICES):
                return Response({'success': False, 'error': 'Invalid decision value'}, status=400)
            app.decision = decision
            if decision == 'approve':
                app.status = 'completed'
                # Transition / Auto-transition to standard Tenant:
                # 1. Create/Get standard user with applicant_email
                from django.contrib.auth.models import User
                from .models import TenantAssignment
                
                user = User.objects.filter(email=app.applicant_email).first()
                if not user:
                    username = app.applicant_email.split('@')[0] + secrets.token_hex(3)
                    # Ensure username is unique
                    while User.objects.filter(username=username).exists():
                        username = app.applicant_email.split('@')[0] + secrets.token_hex(3)
                    
                    user = User.objects.create(
                        email=app.applicant_email,
                        username=username,
                        first_name=app.applicant_name.split(' ')[0],
                        last_name=' '.join(app.applicant_name.split(' ')[1:]) if ' ' in app.applicant_name else ''
                    )
                    user.set_unusable_password()
                    user.save()
                
                # Check if TenantAssignment already exists
                assignment_exists = TenantAssignment.objects.filter(
                    tenant=user,
                    room=app.property_room,
                    status='active'
                ).exists()
                
                if not assignment_exists:
                    from decimal import Decimal
                    TenantAssignment.objects.create(
                        tenant=user,
                        room=app.property_room,
                        property_name=app.property_room.location,
                        start_date=timezone.now().date(),
                        monthly_rent=app.property_room.price,
                        deposit=app.property_room.price * Decimal('1.5'),
                        status='pending',
                        notes=f"Created automatically from approved referencing application #{app.id}."
                    )
            elif decision == 'decline':
                app.status = 'failed'
            app.resolved_at = timezone.now()

        if landlord_notes is not None:
            app.landlord_override_notes = landlord_notes

        if status_val:
            if status_val not in dict(ReferencingApplication.STATUS_CHOICES):
                return Response({'success': False, 'error': 'Invalid status value'}, status=400)
            app.status = status_val

        app.save()
        return Response({'success': True, 'data': serializers.ReferencingApplicationSerializer(app).data})


class PublicReferencingDetailView(APIView):
    permission_classes = [] # Public view
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def get(self, request, token):
        try:
            app = ReferencingApplication.objects.get(token=token, is_archived_or_deleted=False)
        except ReferencingApplication.DoesNotExist:
            return Response({'success': False, 'error': 'Invalid referencing token'}, status=404)
        return Response({'success': True, 'data': serializers.ReferencingApplicationSerializer(app).data})

    def post(self, request, token):
        try:
            app = ReferencingApplication.objects.get(token=token, is_archived_or_deleted=False)
        except ReferencingApplication.DoesNotExist:
            return Response({'success': False, 'error': 'Invalid referencing token'}, status=404)

        # Save tenant submission data
        application_data = request.data.get('application_data', {})
        uploaded_documents = request.data.get('uploaded_documents', [])

        app.application_data = application_data
        app.uploaded_documents = uploaded_documents
        app.status = 'submitted'
        app.save()

        # Trigger AI Background checks immediately (or simulate/schedule)
        from .services.document_extractor import process_referencing_checks
        try:
            process_referencing_checks(app)
        except Exception as e:
            # Let the status still be submitted, but log the check error
            app.landlord_override_notes = f"Auto-checks error: {str(e)}"
            app.save()

        return Response({'success': True, 'data': serializers.ReferencingApplicationSerializer(app).data})


class ReferencingDocumentUploadView(APIView):
    permission_classes = [] # Allow public application upload
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'success': False, 'error': 'No file uploaded'}, status=400)

        # Bump file size limit to 10MB (10 * 1024 * 1024)
        max_size = 10 * 1024 * 1024
        if uploaded_file.size > max_size:
            return Response({'success': False, 'error': 'File exceeds maximum 10MB limit'}, status=400)

        # Validate file extensions
        ext = uploaded_file.name.split('.')[-1].lower()
        allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'webp'}
        if ext not in allowed_extensions:
            return Response({'success': False, 'error': f'Unsupported file format .{ext}'}, status=400)

        from core.storage_backends import supabase_storage
        try:
            # Upload to private bucket
            public_url = supabase_storage.upload_document(uploaded_file, bucket_name='documents', folder='referencing')
            
            # Extract private path
            path_marker = "/object/public/documents/"
            if path_marker in public_url:
                file_path = public_url.split(path_marker)[-1]
            else:
                file_path = f"referencing/{public_url.split('/')[-1].split('?')[0]}"
            
            # Generate a 60-minute signed URL
            signed_url = supabase_storage.create_signed_url(file_path, bucket_name='documents', expires_in=3600)
            
            return Response({
                'success': True,
                'file_url': signed_url,
                'file_path': file_path,
                'file_name': uploaded_file.name
            })
        except Exception as e:
            # Fallback to local storage if Supabase is not configured
            from django.core.files.storage import default_storage
            file_path = default_storage.save(f'referencing_docs/{secrets.token_hex(8)}_{uploaded_file.name}', uploaded_file)
            file_url = request.build_absolute_uri(settings.MEDIA_URL + file_path)
            return Response({
                'success': True,
                'file_url': file_url,
                'file_path': file_path,
                'file_name': uploaded_file.name
            })


class GenerateReferencingReportView(APIView):
    """Landlord-only: Generate a PDF referencing report for a given application."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request, pk):
        try:
            app = ReferencingApplication.objects.select_related('property_room').get(pk=pk, is_archived_or_deleted=False)
        except ReferencingApplication.DoesNotExist:
            return Response({'success': False, 'error': 'Application not found'}, status=404)

        if app.status == 'invited':
            return Response({'success': False, 'error': 'Cannot generate report before applicant has submitted.'}, status=400)

        from .services.report_generator import generate_referencing_report_pdf
        try:
            report_url = generate_referencing_report_pdf(app)
            # Refresh from DB to get the stored file_path
            app.refresh_from_db()
            return Response({
                'success': True,
                'report_pdf_url': report_url,
                'report_file_path': app.report_pdf_url,
                'data': serializers.ReferencingApplicationSerializer(app).data
            })
        except Exception as e:
            return Response({'success': False, 'error': f'Failed to generate report: {str(e)}'}, status=500)


class DownloadReferencingReportView(APIView):
    """
    Landlord-only: Download the PDF referencing report for a given application.
    Generates a fresh signed URL for Supabase-stored files, or serves local files
    with proper Content-Disposition headers.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            app = ReferencingApplication.objects.select_related('property_room').get(pk=pk, is_archived_or_deleted=False)
        except ReferencingApplication.DoesNotExist:
            return Response({'success': False, 'error': 'Application not found'}, status=404)

        if not app.report_pdf_url:
            return Response({'success': False, 'error': 'No report has been generated yet.'}, status=404)

        stored_path = app.report_pdf_url

        # Case 1: Supabase file path (e.g. "referencing_reports/xxx.pdf")
        if stored_path.startswith('referencing_reports/'):
            from core.storage_backends import supabase_storage
            signed_url = supabase_storage.create_signed_url(
                stored_path, bucket_name='documents', expires_in=3600
            )
            if signed_url:
                return Response({
                    'success': True,
                    'download_url': signed_url,
                    'file_name': f'referencing_report_{app.id}.pdf',
                    'content_type': 'application/pdf',
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to generate download URL. The file may no longer exist in storage.'
                }, status=500)

        # Case 2: Local file path (e.g. "/media/referencing_reports/xxx.pdf")
        import os
        from django.conf import settings as django_settings
        from django.http import FileResponse

        if stored_path.startswith(django_settings.MEDIA_URL):
            # Strip the MEDIA_URL prefix to get relative path
            relative_path = stored_path[len(django_settings.MEDIA_URL):]
            absolute_path = os.path.join(django_settings.MEDIA_ROOT, relative_path)
        else:
            absolute_path = os.path.join(django_settings.MEDIA_ROOT, stored_path)

        if os.path.exists(absolute_path):
            response = FileResponse(
                open(absolute_path, 'rb'),
                content_type='application/pdf',
            )
            response['Content-Disposition'] = f'attachment; filename="referencing_report_{app.id}.pdf"'
            return response

        # Case 3: Legacy signed URL (still valid or expired)
        if stored_path.startswith('http'):
            return Response({
                'success': True,
                'download_url': stored_path,
                'file_name': f'referencing_report_{app.id}.pdf',
                'content_type': 'application/pdf',
                'warning': 'This is a legacy URL that may have expired. Consider regenerating the report.'
            })

        return Response({
            'success': False,
            'error': 'Report file could not be located. Please regenerate the report.'
        }, status=404)


# ── Stripe Payment Views ──────────────────────────────────────────────

class StripeCheckoutSessionView(APIView):
    """
    Create a Stripe Checkout Session for a pending RentPayment.
    POST body: { "payment_id": 123, "success_url": "...", "cancel_url": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import RentPayment
        from .services.stripe_services import create_checkout_session

        payment_id = request.data.get('payment_id')
        if not payment_id:
            return Response({'success': False, 'error': 'payment_id is required'}, status=400)

        try:
            payment = RentPayment.objects.select_related('schedule').get(pk=payment_id)
        except RentPayment.DoesNotExist:
            return Response({'success': False, 'error': 'Payment not found'}, status=404)

        if payment.status == 'paid':
            return Response({'success': False, 'error': 'Payment is already paid'}, status=400)

        success_url = request.data.get('success_url', request.build_absolute_uri('/'))
        cancel_url = request.data.get('cancel_url', request.build_absolute_uri('/'))

        try:
            session = create_checkout_session(payment, success_url, cancel_url)
            return Response({
                'success': True,
                'checkout_url': session.url,
                'session_id': session.id,
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=500)


class StripeWebhookView(APIView):
    """
    Stripe webhook endpoint to handle payment events.
    Verifies signature if STRIPE_WEBHOOK_SECRET is set, otherwise accepts raw payload (dev mode).
    """
    permission_classes = []  # No auth — Stripe calls this
    authentication_classes = []

    def post(self, request):
        import stripe
        from django.conf import settings
        from .models import RentPayment

        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

        event = None

        if webhook_secret:
            try:
                event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            except ValueError:
                return Response({'error': 'Invalid payload'}, status=400)
            except stripe.error.SignatureVerificationError:
                return Response({'error': 'Invalid signature'}, status=400)
        else:
            # Dev mode: parse event without signature verification
            import json
            try:
                event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
            except Exception:
                return Response({'error': 'Could not parse event'}, status=400)

        # Handle checkout.session.completed
        if event and event.type == 'checkout.session.completed':
            session = event.data.object
            payment_id = getattr(session, 'client_reference_id', None) or (getattr(session, 'metadata', {}) or {}).get('payment_id')

            if payment_id:
                try:
                    payment = RentPayment.objects.get(pk=int(payment_id))
                    payment.status = 'paid'
                    payment.paid_amount = payment.amount
                    payment.paid_date = timezone.now().date()
                    payment.payment_method = 'stripe'
                    payment.stripe_payment_intent_id = str(getattr(session, 'payment_intent', '') or '')
                    payment.save(update_fields=[
                        'status', 'paid_amount', 'paid_date',
                        'payment_method', 'stripe_payment_intent_id'
                    ])
                except RentPayment.DoesNotExist:
                    pass

        return Response({'status': 'ok'})


class StripePaymentSuccessView(APIView):
    """
    Called by the frontend after returning from Stripe Checkout.
    Verifies the session and marks payment as paid if not already handled by webhook.
    GET ?session_id=cs_xxx
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import stripe
        import logging
        logger = logging.getLogger(__name__)
        from django.conf import settings
        from .models import RentPayment

        stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        if not stripe_key:
            logger.error("[StripePaymentSuccessView] STRIPE_SECRET_KEY is missing from settings.")
            return Response({'success': False, 'error': 'Stripe secret key is missing from backend configuration.'}, status=500)

        stripe.api_key = stripe_key
        session_id = request.query_params.get('session_id')

        if not session_id:
            return Response({'success': False, 'error': 'session_id is required'}, status=400)

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception as e:
            logger.error(f"[StripePaymentSuccessView] Stripe session.retrieve failed: {str(e)}")
            return Response({'success': False, 'error': f'Stripe retrieve error: {str(e)}'}, status=400)

        if session.payment_status != 'paid':
            logger.warning(f"[StripePaymentSuccessView] Session {session_id} payment status is '{session.payment_status}' instead of 'paid'")
            return Response({'success': False, 'error': f'Payment status is {session.payment_status}', 'payment_status': session.payment_status}, status=402)

        payment_id = session.client_reference_id or (session.metadata or {}).get('payment_id')
        if not payment_id:
            logger.error(f"[StripePaymentSuccessView] Session {session_id} has no client_reference_id or payment_id in metadata")
            return Response({'success': False, 'error': 'Could not identify payment record from session'}, status=400)

        try:
            payment = RentPayment.objects.get(pk=int(payment_id))
        except RentPayment.DoesNotExist:
            logger.error(f"[StripePaymentSuccessView] RentPayment #{payment_id} not found")
            return Response({'success': False, 'error': f'Payment #{payment_id} record not found'}, status=404)

        if payment.status != 'paid':
            payment.status = 'paid'
            payment.paid_amount = payment.amount
            payment.paid_date = timezone.now().date()
            payment.payment_method = 'stripe'
            payment.stripe_payment_intent_id = getattr(session, 'payment_intent', '') or ''
            payment.save(update_fields=[
                'status', 'paid_amount', 'paid_date',
                'payment_method', 'stripe_payment_intent_id'
            ])
            logger.info(f"[StripePaymentSuccessView] Marked RentPayment #{payment.id} as PAID via Stripe session {session_id}")

        return Response({
            'success': True,
            'message': 'Payment confirmed',
            'payment_id': payment.id,
            'status': payment.status,
        })
