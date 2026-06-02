from rest_framework.throttling import AnonRateThrottle


class WompiWebhookRateThrottle(AnonRateThrottle):
    scope = "wompi_webhook"
