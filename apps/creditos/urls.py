# urls.py
from rest_framework.routers import DefaultRouter

from .views import CreditoViewSet, CuotaCreditoViewSet

router = DefaultRouter()
router.register(r"creditos", CreditoViewSet, basename="credito")
router.register(r"cuotas", CuotaCreditoViewSet, basename="cuota-credito")

urlpatterns = router.urls
