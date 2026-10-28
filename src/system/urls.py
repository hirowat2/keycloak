"""
URL configuration for pseudoproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path, re_path

from proposal import views
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

# from debug_toolbar.toolbar import debug_toolbar_urls
import sys

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from proposal import views

urlpatterns = (
    [
        path("", include("django_prometheus.urls")),
        path("", include("django_components.urls")),
        path("", include("pwa.urls")),
        path("admin/", admin.site.urls),
        path("", include("proposal.landing")),
        path("app/", include("proposal.app")),
        path(r"health/", include("health_check.urls")),
        path("silk/", include("silk.urls", namespace="silk")),
        # /media/ também com DEBUG desligado (CSS, JS e imagens do layout ficam aí).
        re_path(r"^media/(?P<path>.+)$", views.media, name="media"),
    ]
    # + debug_toolbar_urls()
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)

if "test" not in sys.argv:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
