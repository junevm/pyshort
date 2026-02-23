from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter

from shortener import views
from shortener.api_views import APIKeyViewSet, ShortenedURLViewSet

router = DefaultRouter()
router.register(r'links', ShortenedURLViewSet, basename='api-links')
router.register(r'apikeys', APIKeyViewSet, basename='api-keys')

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create/', views.create_link, name='create_link'),
    path('edit/<int:pk>/', views.edit_link, name='edit_link'),
    path('delete/<int:pk>/', views.delete_link, name='delete_link'),
    path('analytics/<int:pk>/', views.analytics, name='analytics'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/register/', views.register, name='register'),
    path('api/', include(router.urls)),
    path('<str:short_code>/', views.redirect_url, name='redirect_url'),
]
