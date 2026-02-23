import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class BlacklistedDomain(models.Model):
    domain = models.CharField(max_length=255, unique=True)
    added_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)

    def __str__(self):
        return self.domain

    class Meta:
        ordering = ['domain']


class ShortenedURL(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='shortened_urls')
    original_url = models.URLField(max_length=2048)
    short_code = models.CharField(max_length=20, unique=True, db_index=True)
    custom_alias = models.CharField(max_length=50, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.short_code} -> {self.original_url[:50]}"

    @property
    def effective_code(self):
        return self.custom_alias if self.custom_alias else self.short_code

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def increment_click(self):
        self.click_count += 1
        self.save(update_fields=['click_count'])

    class Meta:
        ordering = ['-created_at']


class ClickEvent(models.Model):
    shortened_url = models.ForeignKey(ShortenedURL, on_delete=models.CASCADE, related_name='click_events')
    clicked_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(max_length=2048, blank=True)

    def __str__(self):
        return f"Click on {self.shortened_url.short_code} at {self.clicked_at}"

    class Meta:
        ordering = ['-clicked_at']


class APIKey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    key = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = uuid.uuid4().hex + uuid.uuid4().hex
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
