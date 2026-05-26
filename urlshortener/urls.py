from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shortener.urls')),
]

# Custom 404 handler (Stage 1 enhancement) gives expired / missing links a
# branded page instead of Django's default debug-only response.
handler404 = 'shortener.views.custom_404'
