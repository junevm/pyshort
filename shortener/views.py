import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from shortener import ratelimit
from shortener.forms import LinkPasswordForm, RegisterForm, ShortenURLForm
from shortener.models import ClickEvent, ShortenedURL
from shortener.security import is_safe_redirect_url
from shortener.utils import build_qr_png, generate_unique_short_code, get_client_ip

logger = logging.getLogger(__name__)

# --- Rate-limit budgets (key, limit, window seconds) -------------------------
RL_CREATE = ('create', 20, 60)        # 20 creations / minute / ip
RL_REDIRECT = ('redirect', 120, 60)   # 120 hits / minute / ip on /<code>/
RL_PASSWORD = ('password', 10, 300)   # 10 password attempts / 5min / ip+code


def _rl_key(request, prefix: str, suffix: str = '') -> str:
    return f"{prefix}:{get_client_ip(request) or 'anon'}:{suffix}"


def _short_url_for(request, obj) -> str:
    base = request.build_absolute_uri('/').rstrip('/')
    return f"{base}/{obj.effective_code}/"


# -----------------------------------------------------------------------------
# Public pages
# -----------------------------------------------------------------------------
def home(request):
    form = ShortenURLForm()
    short_url = None
    if request.method == 'POST':
        prefix, limit, window = RL_CREATE
        if not ratelimit.allow(_rl_key(request, prefix), limit, window):
            messages.error(request, "Too many requests. Please slow down and try again.")
            return render(request, 'shortener/home.html', {'form': form, 'short_url': None})

        form = ShortenURLForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            if request.user.is_authenticated:
                obj.user = request.user
            obj.short_code = generate_unique_short_code()
            raw_password = form.cleaned_data.get('password') or ''
            if raw_password:
                obj.set_password(raw_password)
            obj.save()
            short_url = _short_url_for(request, obj)
            messages.success(request, f"Short URL created: {short_url}")
            logger.info("Created short link %s for user=%s",
                        obj.effective_code, getattr(obj.user, 'username', 'anon'))
    return render(request, 'shortener/home.html', {'form': form, 'short_url': short_url})


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


# -----------------------------------------------------------------------------
# Owner-only CRUD
# -----------------------------------------------------------------------------
@login_required
def dashboard(request):
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status', 'all')   # all | active | inactive | expired
    sort = request.GET.get('sort', 'recent')    # recent | oldest | clicks | code

    links = ShortenedURL.objects.filter(user=request.user)
    if q:
        links = links.filter(
            Q(original_url__icontains=q)
            | Q(short_code__icontains=q)
            | Q(custom_alias__icontains=q)
            | Q(description__icontains=q)
        )
    if status == 'active':
        links = links.filter(is_active=True)
    elif status == 'inactive':
        links = links.filter(is_active=False)
    elif status == 'expired':
        from django.utils import timezone
        links = links.filter(expires_at__lt=timezone.now())

    sort_map = {
        'recent': '-created_at',
        'oldest': 'created_at',
        'clicks': '-click_count',
        'code': 'short_code',
    }
    links = links.order_by(sort_map.get(sort, '-created_at'))

    paginator = Paginator(links, 15)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'shortener/dashboard.html', {
        'page': page,
        'links': page.object_list,
        'q': q, 'status': status, 'sort': sort,
        'total': paginator.count,
    })


@login_required
def create_link(request):
    form = ShortenURLForm()
    if request.method == 'POST':
        prefix, limit, window = RL_CREATE
        if not ratelimit.allow(_rl_key(request, prefix), limit, window):
            messages.error(request, "Too many requests. Please slow down and try again.")
            return render(request, 'shortener/link_form.html',
                          {'form': form, 'action': 'Create'})
        form = ShortenURLForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.short_code = generate_unique_short_code()
            raw_password = form.cleaned_data.get('password') or ''
            if raw_password:
                obj.set_password(raw_password)
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
    return render(request, 'shortener/link_form.html',
                  {'form': form, 'action': 'Edit', 'link': link})


@login_required
@require_http_methods(["GET", "POST"])
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
    return render(request, 'shortener/analytics.html',
                  {'link': link, 'click_events': click_events,
                   'share_url': _short_url_for(request, link)})


@login_required
def qr_code(request, pk):
    """Return a PNG QR code for the owner's short link."""
    link = get_object_or_404(ShortenedURL, pk=pk, user=request.user)
    png = build_qr_png(_short_url_for(request, link))
    response = HttpResponse(png, content_type='image/png')
    response['Cache-Control'] = 'private, max-age=300'
    response['Content-Disposition'] = f'inline; filename="{link.effective_code}.png"'
    return response


# -----------------------------------------------------------------------------
# Redirect (the hot path)
# -----------------------------------------------------------------------------
def _lookup(short_code: str):
    """Find an active link by alias first, then short_code."""
    return (ShortenedURL.objects.filter(custom_alias=short_code, is_active=True).first()
            or ShortenedURL.objects.filter(short_code=short_code, is_active=True).first())


def _record_click(request, obj):
    obj.register_click()
    ClickEvent.objects.create(
        shortened_url=obj,
        ip_address=get_client_ip(request) or None,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        referrer=request.META.get('HTTP_REFERER', '')[:2048],
    )


def redirect_url(request, short_code):
    prefix, limit, window = RL_REDIRECT
    if not ratelimit.allow(_rl_key(request, prefix), limit, window):
        return HttpResponse("Rate limit exceeded.", status=429)

    obj = _lookup(short_code)
    if not obj:
        raise Http404("Short URL not found.")
    if obj.is_expired or obj.is_exhausted:
        raise Http404("This short URL is no longer available.")
    if not is_safe_redirect_url(obj.original_url):
        logger.error("Refusing to redirect to unsafe URL: %r", obj.original_url)
        raise Http404("Unsafe target URL.")

    if obj.has_password:
        unlocked = request.session.get('unlocked_links', [])
        if obj.pk not in unlocked:
            return redirect('password_gate', short_code=short_code)

    _record_click(request, obj)
    return HttpResponseRedirect(obj.original_url)


@require_http_methods(["GET", "POST"])
def password_gate(request, short_code):
    obj = _lookup(short_code)
    if not obj or not obj.has_password:
        raise Http404("Short URL not found.")
    if obj.is_expired or obj.is_exhausted:
        raise Http404("This short URL is no longer available.")

    form = LinkPasswordForm(request.POST or None)
    error = None
    if request.method == 'POST':
        prefix, limit, window = RL_PASSWORD
        if not ratelimit.allow(_rl_key(request, prefix, short_code), limit, window):
            error = "Too many attempts. Please wait a few minutes."
        elif form.is_valid():
            if obj.check_password(form.cleaned_data['password']):
                unlocked = request.session.get('unlocked_links', [])
                if obj.pk not in unlocked:
                    unlocked.append(obj.pk)
                    request.session['unlocked_links'] = unlocked
                _record_click(request, obj)
                return HttpResponseRedirect(obj.original_url)
            error = "Incorrect password."
    return render(request, 'shortener/password_gate.html',
                  {'form': form, 'link': obj, 'error': error})


# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------
def custom_404(request, exception=None):
    return render(request, 'shortener/404.html', status=404)
