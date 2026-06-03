from django.urls import path

from . import views

urlpatterns = [
    path("carrito/", views.CarritoView.as_view()),
    path("carrito/productos/", views.ProductoCarritoView.as_view()),
    path("carrito/productos/<int:producto_id>/", views.ProductoCarritoView.as_view()),
    path("checkout/", views.CheckoutView.as_view()),
    path("pedidos/<int:pedido_id>/", views.PedidoDetalleView.as_view()),
    path("pedidos/<int:pedido_id>/pagar/", views.IniciarPagoPedidoView.as_view()),
    path("pedidos/pending/", views.DeletePendingPedidoView.as_view()),
    path("mis-pedidos/", views.PedidoListView.as_view()),
    path("webhooks/wompi/", views.WompiWebhookView.as_view()),
    path("admin/pedidos/", views.AdminPedidoListView.as_view()),
    path("admin/pedidos/presencial/", views.PedidoPresencialView.as_view()),
    path(
        "admin/pedidos/<int:pedido_id>/cancelar/",
        views.AdminCancelarPedidoView.as_view(),
    ),
    path(
        "admin/pedidos/<int:pedido_id>/confirmar-pago/",
        views.ConfirmarPagoManualView.as_view(),
    ),
    path(
        "admin/pedidos/<int:pedido_id>/credito/",
        views.PedidoCreditoView.as_view(),
    ),
]
