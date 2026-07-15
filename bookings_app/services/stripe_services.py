import stripe
from django.conf import settings

stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)

def create_checkout_session(payment, success_url: str, cancel_url: str):
    """
    Create a Stripe Checkout Session for a RentPayment.
    """
    if not stripe.api_key:
        raise ValueError("Stripe API key is not configured in backend settings.")

    # Convert decimal amount to cents (integer)
    amount_in_cents = int(payment.amount * 100)

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'gbp',
                'product_data': {
                    'name': f"Rent Payment for {payment.schedule.room_name}",
                    'description': f"Due date: {payment.due_date.strftime('%B %d, %Y')}",
                },
                'unit_amount': amount_in_cents,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(payment.id),
        metadata={
            'payment_id': str(payment.id),
            'schedule_id': str(payment.schedule.id),
        }
    )

    # Save checkout session details to the payment record
    payment.stripe_checkout_session_id = session.id
    payment.save(update_fields=['stripe_checkout_session_id'])

    return session
