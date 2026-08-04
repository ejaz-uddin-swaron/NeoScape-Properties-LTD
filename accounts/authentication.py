import jwt
from functools import lru_cache
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication, exceptions
from jwt import InvalidTokenError, PyJWKClient
from .models import Client


def _normalize_url(url: str) -> str:
    return (url or '').rstrip('/')


@lru_cache(maxsize=1)
def _get_jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def _decode_supabase_jwt(token: str) -> dict:
    supabase_url = _normalize_url(getattr(settings, 'SUPABASE_URL', ''))
    jwt_secret = getattr(settings, 'SUPABASE_JWT_SECRET', '')
    audience = getattr(settings, 'SUPABASE_JWT_AUDIENCE', 'authenticated')
    issuer = f'{supabase_url}/auth/v1' if supabase_url else None

    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise exceptions.AuthenticationFailed(f'Invalid token header: {exc}')

    alg = header.get('alg')
    if not alg:
        raise exceptions.AuthenticationFailed('Token header missing "alg".')

    decode_kwargs = {
        'algorithms': [alg],
        'options': {
            'verify_exp': True,
            'verify_sub': True,
            'verify_aud': bool(audience),
            'verify_iss': bool(issuer),
        },
    }

    if audience:
        decode_kwargs['audience'] = audience
    if issuer:
        decode_kwargs['issuer'] = issuer

    try:
        if alg.startswith('HS'):
            if not jwt_secret:
                raise exceptions.AuthenticationFailed(
                    'SUPABASE_JWT_SECRET is required for HS* tokens.'
                )
            return jwt.decode(token, jwt_secret, **decode_kwargs)

        if alg.startswith('RS') or alg.startswith('ES'):
            if not supabase_url:
                raise exceptions.AuthenticationFailed(
                    'SUPABASE_URL is required for JWKS validation.'
                )

            jwks_url = f'{supabase_url}/auth/v1/.well-known/jwks.json'
            signing_key = _get_jwk_client(jwks_url).get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, **decode_kwargs)

        raise exceptions.AuthenticationFailed(f'Unsupported JWT algorithm: {alg}')
    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailed('Token has expired.')
    except InvalidTokenError as exc:
        raise exceptions.AuthenticationFailed(f'Invalid token: {exc}')


class SupabaseAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')
        token = parts[1]

        payload = _decode_supabase_jwt(token)

        # Extract user data from the payload
        # Supabase stores the unique user UUID in the 'sub' claim
        supabase_id = payload.get('sub')
        email = payload.get('email')
        
        if not supabase_id:
            raise exceptions.AuthenticationFailed('Token payload missing "sub" claim.')

        # Metadata often contains names
        user_metadata = payload.get('user_metadata', {})
        first_name = user_metadata.get('full_name', '').split(' ')[0] if user_metadata.get('full_name') else ''
        last_name = ' '.join(user_metadata.get('full_name', '').split(' ')[1:]) if user_metadata.get('full_name') else ''
        app_metadata = payload.get('app_metadata', {})
        role = app_metadata.get('role') or user_metadata.get('role') or 'customer'
        if role not in {'customer', 'tenant', 'admin'}:
            role = 'customer'

        # Get or create the Django User
        # We use the Supabase UUID as the username to ensure uniqueness across providers (Discord, Google, etc)
        user, created = User.objects.get_or_create(
            username=supabase_id,
            defaults={
                'email': email or '',
                'first_name': first_name,
                'last_name': last_name
            }
        )
        
        # If the user already existed, update their email if it changed in Supabase
        user_updated = False
        if email and user.email != email:
            user.email = email
            user_updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            user_updated = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            user_updated = True
        if user_updated:
            user.save(update_fields=['email', 'first_name', 'last_name'])

        # Ensure the Client profile exists
        if not hasattr(user, 'client'):
            Client.objects.create(
                user=user,
                role=role,
                mobile_no='',
                image=''
            )

        return (user, token)

    def authenticate_header(self, request):
        return 'Bearer'
