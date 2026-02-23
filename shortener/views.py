from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from shortener.forms import RegisterForm, ShortenURLForm
from shortener.models import ClickEvent, ShortenedURL
from shortener.utils import generate_unique_short_code, get_client_ip


def home(request):
    form = ShortenURLForm()
    short_url = None
    if request.method == 'POST':
        form = ShortenURLForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            if request.user.is_authenticated:
                obj.user = request.user
            obj.short_code = generate_unique_short_code()
            obj.save()
            base = request.build_absolute_uri('/').rstrip('/')
            code = obj.custom_alias if obj.custom_alias else obj.short_code
            short_url = f"{base}/{code}/"
            messages.success(request, f"Short URL created: {short_url}")
    return render(request, 'shortener/home.html', {'form': form, 'short_url': short_url})


@login_required
def dashboard(request):
    links = ShortenedURL.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'shortener/dashboard.html', {'links': links})


@login_required
def create_link(request):
    form = ShortenURLForm()
    if request.method == 'POST':
        form = ShortenURLForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.short_code = generate_unique_short_code()
            obj.save()
            messages.success(request, "Short link created successfully.")
            return redirect('dashboard')
    return render(request, 'shortener/link_form.html', {'form': form, 'action': 'Create'})


@login_required
def edit_link(request, pk):
    link = get_object_or_404(ShortenedURL, pk=pk, user=request.user)
    form = ShortenURLForm(instance=link)
    if request.method == 'POST':
        form = ShortenURLForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, "Link updated successfully.")
            return redirect('dashboard')
    return render(request, 'shortener/link_form.html', {'form': form, 'action': 'Edit', 'link': link})


@login_required
def delete_link(request, pk):
    link = get_object_or_404(ShortenedURL, pk=pk, user=request.user)
    if request.method == 'POST':
        link.delete()
        messages.success(request, "Link deleted successfully.")
        return redirect('dashboard')
    return render(request, 'shortener/confirm_delete.html', {'link': link})


@login_required
def analytics(request, pk):
    link = get_object_or_404(ShortenedURL, pk=pk, user=request.user)
    click_events = link.click_events.order_by('-clicked_at')[:100]
    return render(request, 'shortener/analytics.html', {'link': link, 'click_events': click_events})


def redirect_url(request, short_code):
    obj = ShortenedURL.objects.filter(custom_alias=short_code, is_active=True).first()
    if not obj:
        obj = ShortenedURL.objects.filter(short_code=short_code, is_active=True).first()
    if not obj:
        raise Http404("Short URL not found.")
    if obj.is_expired:
        raise Http404("This short URL has expired.")
    obj.increment_click()
    ClickEvent.objects.create(
        shortened_url=obj,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        referrer=request.META.get('HTTP_REFERER', '')[:2048],
    )
    return redirect(obj.original_url)


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm()
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Welcome.")
            return redirect('dashboard')
    return render(request, 'registration/register.html', {'form': form})
