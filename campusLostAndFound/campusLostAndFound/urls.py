"""
URL configuration for campusLostAndFound project.
Routes admin, core items app, Django auth, and media uploads.
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    # Admin Portal
    path('admin/', admin.site.urls),
    
    # Core Application Routes
    path('', include('items.urls')),
    
    # Built-in Authentication (login, logout, password change)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Media file serving across development and cloud environments
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
