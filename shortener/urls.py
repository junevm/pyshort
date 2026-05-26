from django.contrib.auth import views as auth_views
from django.urls import path

from shortener import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create/', views.create_link, name='create_link'),
    path('edit/<int:pk>/', views.edit_link, name='edit_link'),
    path('delete/<int:pk>/', views.delete_link, name='delete_link'),
    path('analytics/<int:pk>/', views.analytics, name='analytics'),
    path('qr/<int:pk>.png', views.qr_code, name='qr_code'),

    path('accounts/login/',
         auth_views.LoginView.as_view(template_name='registration/login.html'),
         name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/register/', views.register, name='register'),

    # Password gate is mounted at a deeper path so it never collides with
    # legitimate short codes (which match [A-Za-z0-9_-]+ only).
    path('password/<str:short_code>/', views.password_gate, name='password_gate'),

    # MUST be the very last pattern.
    path('<str:short_code>/', views.redirect_url, name='redirect_url'),
]
