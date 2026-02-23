from django.urls import path
from django.contrib.auth import views as auth_views

from shortener import views

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
    path('<str:short_code>/', views.redirect_url, name='redirect_url'),
]
