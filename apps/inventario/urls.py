from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

router = DefaultRouter()
router.register(r'ingredientes', views.IngredienteViewSet, basename='ingrediente')
router.register(r'productos', views.ProductoViewSet, basename='producto')
router.register(r'producto-ingredientes', views.ProductoIngredienteViewSet, basename='producto-ingrediente')
router.register(r'movimientos-ingrediente', views.MovimientoIngredienteViewSet, basename='movimiento-ingrediente')
router.register(r'movimientos-producto', views.MovimientoProductoViewSet, basename='movimiento-producto')

urlpatterns = [
    path('public/productos/', views.ProductoPublicAPIView.as_view(), name='public-productos'),
    path('public/ingredientes/', views.IngredientePublicAPIView.as_view(), name='public-ingredientes'),
    path('public/producto-ingredientes/', views.ProductoIngredientePublicAPIView.as_view(), name='public-producto-ingredientes'),
    path('', include(router.urls)),
    path('producciones/proximas-a-vencer/', views.ProduccionesProximasVencerAPIView.as_view(), name='producciones-proximas-a-vencer'),
    path('producciones/', views.ProduccionAPIView.as_view(), name='producciones'),
]
