from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginThrottle

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)
BLOCK_DURATION = timedelta(minutes=15)


def _client_key(request):
    # Caddy menambahkan alamat klien di ujung kanan X-Forwarded-For.
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    address = forwarded_for.split(",")[-1].strip() if forwarded_for else ""
    address = address or request.META.get("REMOTE_ADDR", "unknown")
    return salted_hmac("accounts.login-throttle", address, secret=settings.SECRET_KEY).hexdigest()


def blocked_until(request):
    key = _client_key(request)
    now = timezone.now()
    attempt = LoginThrottle.objects.filter(key=key).first()
    if attempt is None:
        return None
    if attempt.updated_at <= now - WINDOW:
        attempt.delete()
        return None
    if attempt.blocked_until and attempt.blocked_until > now:
        return attempt.blocked_until
    return None


def record_failure(request):
    key = _client_key(request)
    now = timezone.now()
    LoginThrottle.objects.filter(updated_at__lte=now - WINDOW).delete()
    with transaction.atomic():
        attempt, _ = LoginThrottle.objects.select_for_update().get_or_create(
            key=key,
            defaults={"window_started": now},
        )
        if attempt.window_started <= now - WINDOW:
            attempt.failures = 0
            attempt.window_started = now
        attempt.failures += 1
        if attempt.failures >= MAX_FAILURES:
            attempt.blocked_until = now + BLOCK_DURATION
        attempt.save(update_fields=["failures", "window_started", "blocked_until", "updated_at"])
    return attempt.blocked_until


def clear_failures(request):
    LoginThrottle.objects.filter(key=_client_key(request)).delete()
