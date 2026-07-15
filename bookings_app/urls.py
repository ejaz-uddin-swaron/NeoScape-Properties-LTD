from django.urls import path
from .views import (
    BookingsView, UpdateBookingStatusView,
    RentScheduleView, RentScheduleDetailView, RentPaymentView, RentReminderView,
    TenantAssignmentListView, TenantAssignmentDetailView, MyAssignmentView,
    MyRentSchedulesView, MyRentRemindersView,
    ChatChannelView, ChatMessageView, GenerateAgreementView,
    TenancyAgreementView, TenancyAgreementDetailView, SignAgreementView,
    ReferencingApplicationListCreateView, ReferencingApplicationDetailView,
    PublicReferencingDetailView, ReferencingDocumentUploadView,
    GenerateReferencingReportView,
    StripeCheckoutSessionView, StripeWebhookView, StripePaymentSuccessView,
)

urlpatterns = [
    path('', BookingsView.as_view(), name='bookings'),  # GET: admin list all bookings
    path('<int:pk>/status/', UpdateBookingStatusView.as_view(), name='update-booking-status'),
    path('rent-schedules/', RentScheduleView.as_view(), name='rent-schedules'),
    path('rent-schedules/<int:pk>/', RentScheduleDetailView.as_view(), name='rent-schedule-detail'),
    path('rent-schedules/<int:schedule_id>/payments/', RentPaymentView.as_view(), name='rent-payments'),
    path('rent-reminders/', RentReminderView.as_view(), name='rent-reminders'),
    # Tenant assignments (admin)
    path('tenant-assignments/', TenantAssignmentListView.as_view(), name='tenant-assignments'),
    path('tenant-assignments/<int:pk>/', TenantAssignmentDetailView.as_view(), name='tenant-assignment-detail'),
    # Tenant self-service
    path('my-assignment/', MyAssignmentView.as_view(), name='my-assignment'),
    path('my-rent-schedules/', MyRentSchedulesView.as_view(), name='my-rent-schedules'),
    path('my-rent-reminders/', MyRentRemindersView.as_view(), name='my-rent-reminders'),
    
    # Chat channels & messages
    path('channels/', ChatChannelView.as_view(), name='chat-channels'),
    path('channels/<int:channel_id>/messages/', ChatMessageView.as_view(), name='chat-messages'),
    
    # AI Agreement Draft Generation
    path('generate-agreement/', GenerateAgreementView.as_view(), name='generate-agreement'),
    
    # Tenancy Agreements & Signing
    path('agreements/', TenancyAgreementView.as_view(), name='agreements-list'),
    path('agreements/<int:pk>/', TenancyAgreementDetailView.as_view(), name='agreement-detail'),
    path('agreements/<int:pk>/sign/', SignAgreementView.as_view(), name='sign-agreement'),

    # Tenant Referencing Module
    path('referencing/', ReferencingApplicationListCreateView.as_view(), name='referencing-list'),
    path('referencing/<int:pk>/', ReferencingApplicationDetailView.as_view(), name='referencing-detail'),
    path('referencing/<int:pk>/report/', GenerateReferencingReportView.as_view(), name='referencing-report'),
    path('referencing/public/<str:token>/', PublicReferencingDetailView.as_view(), name='public-referencing-detail'),
    path('referencing/upload/', ReferencingDocumentUploadView.as_view(), name='referencing-upload'),

    # Stripe Payments
    path('stripe/checkout/', StripeCheckoutSessionView.as_view(), name='stripe-checkout'),
    path('stripe/webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('stripe/success/', StripePaymentSuccessView.as_view(), name='stripe-success'),
]

