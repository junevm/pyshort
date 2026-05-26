from django.contrib import admin

from shortener.models import ClickEvent, ShortenedURL


@admin.register(ShortenedURL)
class ShortenedURLAdmin(admin.ModelAdmin):
    list_display = ['effective_code', 'original_url', 'user', 'click_count',
                    'max_clicks', 'has_password', 'is_active', 'created_at', 'expires_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['short_code', 'custom_alias', 'original_url',
                     'user__username', 'description']
    readonly_fields = ['short_code', 'click_count', 'created_at', 'password_hash']
    fieldsets = (
        (None, {'fields': ('user', 'original_url', 'short_code',
                           'custom_alias', 'description')}),
        ('Lifecycle', {'fields': ('expires_at', 'max_clicks', 'is_active')}),
        ('Stats', {'fields': ('click_count', 'created_at')}),
        ('Security', {'fields': ('password_hash',)}),
    )


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ['shortened_url', 'clicked_at', 'ip_address']
    list_filter = ['clicked_at']
    readonly_fields = ['clicked_at']
    search_fields = ['shortened_url__short_code', 'shortened_url__custom_alias',
                     'ip_address']
