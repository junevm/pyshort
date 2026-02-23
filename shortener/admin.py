from django.contrib import admin
from shortener.models import ClickEvent, ShortenedURL


@admin.register(ShortenedURL)
class ShortenedURLAdmin(admin.ModelAdmin):
    list_display = ['short_code', 'custom_alias', 'original_url', 'user', 'click_count', 'is_active', 'created_at', 'expires_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['short_code', 'custom_alias', 'original_url', 'user__username']
    readonly_fields = ['short_code', 'click_count', 'created_at']


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ['shortened_url', 'clicked_at', 'ip_address']
    list_filter = ['clicked_at']
    readonly_fields = ['clicked_at']
