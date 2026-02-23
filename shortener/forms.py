from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from shortener.models import ShortenedURL


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class ShortenURLForm(forms.ModelForm):
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        help_text="Optional: leave blank for no expiration"
    )

    class Meta:
        model = ShortenedURL
        fields = ['original_url', 'custom_alias', 'expires_at']
        widgets = {
            'original_url': forms.URLInput(attrs={
                'placeholder': 'https://example.com/very-long-url',
                'class': 'form-control',
            }),
            'custom_alias': forms.TextInput(attrs={
                'placeholder': 'my-custom-alias (optional)',
                'class': 'form-control',
            }),
        }

    def clean_custom_alias(self):
        alias = self.cleaned_data.get('custom_alias', '')
        if not alias:
            return alias
        if len(alias) < 3 or len(alias) > 50:
            raise ValidationError("Alias must be between 3 and 50 characters.")
        qs = ShortenedURL.objects.filter(custom_alias=alias)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("This custom alias is already taken.")
        return alias

    def clean_expires_at(self):
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise ValidationError("Expiration date must be in the future.")
        return expires_at
