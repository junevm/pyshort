from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from shortener.models import ShortenedURL
from shortener.security import is_safe_redirect_url, validate_alias


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class ShortenURLForm(forms.ModelForm):
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        help_text="Optional. Leave blank for no expiration.",
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control',
                                          'autocomplete': 'new-password',
                                          'placeholder': 'Optional password gate'}),
        help_text="If set, visitors must enter this password before being redirected.",
        max_length=72,
    )
    max_clicks = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=1_000_000,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0 = unlimited'}),
        help_text="Auto-deactivate after this many clicks. 0 means unlimited.",
    )

    class Meta:
        model = ShortenedURL
        fields = ['original_url', 'custom_alias', 'description', 'expires_at',
                  'max_clicks', 'password']
        widgets = {
            'original_url': forms.URLInput(attrs={
                'placeholder': 'https://example.com/very-long-url',
                'class': 'form-control',
            }),
            'custom_alias': forms.TextInput(attrs={
                'placeholder': 'my-custom-alias (optional)',
                'class': 'form-control',
            }),
            'description': forms.TextInput(attrs={
                'placeholder': 'Internal note (optional)',
                'class': 'form-control',
            }),
        }

    # --- Per-field validation -------------------------------------------------
    def clean_original_url(self):
        url = self.cleaned_data.get('original_url', '').strip()
        if not is_safe_redirect_url(url):
            raise ValidationError("Only http:// and https:// URLs are allowed.")
        return url

    def clean_custom_alias(self):
        alias = (self.cleaned_data.get('custom_alias') or '').strip()
        ok, message = validate_alias(alias)
        if not ok:
            raise ValidationError(message)
        if alias:
            qs = ShortenedURL.objects.filter(custom_alias=alias)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("This custom alias is already taken.")
        return alias or None

    def clean_expires_at(self):
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise ValidationError("Expiration date must be in the future.")
        return expires_at

    def clean_max_clicks(self):
        return self.cleaned_data.get('max_clicks') or 0

    # --- Saving applies password hashing -------------------------------------
    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_password = self.cleaned_data.get('password') or ''
        if raw_password:
            instance.set_password(raw_password)
        elif 'password' in self.changed_data:
            instance.password_hash = ''
        if commit:
            instance.save()
        return instance


class LinkPasswordForm(forms.Form):
    """Used by visitors when accessing a password-protected link."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autofocus': True}),
        max_length=72,
    )
