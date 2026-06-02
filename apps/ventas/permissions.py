from django.conf import settings
from rest_framework.permissions import BasePermission


def obtener_ip_cliente(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class WompiWebhookPermission(BasePermission):
    def has_permission(self, request, view):
        allowed_ips = getattr(settings, "WOMPI_WEBHOOK_ALLOWED_IPS", [])
        if not allowed_ips:
            return True
        return obtener_ip_cliente(request) in allowed_ips
