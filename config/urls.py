from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.views.generic import RedirectView
from core import site_views

from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    #path("", RedirectView.as_view(url="/api/docs/", permanent=False)),
    path("", site_views.home),
    path("", include("core.urls")),
    path("admin/", admin.site.urls),

    # Schema + Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # App APIs
    path("api/", include("core.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)