from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import permissions

from drf_yasg.views import get_schema_view
from drf_yasg import openapi


def root_view(request):
    return JsonResponse({
        "status": "success",
        "message": "NeoScape Properties API is running",
        "version": "1.0.0"
    })


def health_view(request):
    return JsonResponse({
        "status": "ok",
        "timestamp": timezone.now().isoformat()
    })


schema_view = get_schema_view(
    openapi.Info(
        title="NeoScape Properties API",
        default_version='v1',
        description="API documentation for the NeoScape Properties Platform",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    url='https://neo-scape-properties-ltd-nine.vercel.app/' if not settings.DEBUG else None,
)


urlpatterns = [
    path('', root_view, name='root'),
    path('health/', health_view, name='health'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/rooms/', include('rooms.urls')),
    path('api/', include('core.urls')),
    path('api/bookings/', include('bookings_app.urls')),

     # Swagger paths
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
