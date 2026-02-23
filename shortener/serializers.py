from django.utils import timezone
from rest_framework import serializers

from shortener.models import APIKey, ClickEvent, ShortenedURL
from shortener.validators import validate_url, validate_not_blacklisted, validate_custom_alias
from shortener.utils import generate_unique_short_code


class ShortenedURLSerializer(serializers.ModelSerializer):
    short_url = serializers.SerializerMethodField()
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = ShortenedURL
        fields = [
            'id', 'original_url', 'short_code', 'custom_alias',
            'created_at', 'expires_at', 'click_count', 'is_active',
            'is_expired', 'short_url',
        ]
        read_only_fields = ['id', 'short_code', 'created_at', 'click_count', 'is_expired']

    def get_short_url(self, obj):
        request = self.context.get('request')
        code = obj.custom_alias if obj.custom_alias else obj.short_code
        if request:
            return request.build_absolute_uri(f'/{code}/')
        return f'/{code}/'

    def validate_original_url(self, value):
        validate_url(value)
        validate_not_blacklisted(value)
        return value

    def validate_custom_alias(self, value):
        if not value:
            return value
        validate_custom_alias(value)
        instance = self.instance
        qs = ShortenedURL.objects.filter(custom_alias=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This custom alias is already taken.")
        return value

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiration date must be in the future.")
        return value

    def create(self, validated_data):
        validated_data['short_code'] = generate_unique_short_code()
        return super().create(validated_data)


class ClickEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClickEvent
        fields = ['id', 'clicked_at', 'ip_address', 'user_agent', 'referrer']


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ['id', 'name', 'key', 'created_at', 'is_active']
        read_only_fields = ['id', 'key', 'created_at']
