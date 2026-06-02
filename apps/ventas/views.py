import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.usuarios.permissions import IsAdministrador

from . import models, serializers, services
from .pagination import PedidoPagination
from .permissions import WompiWebhookPermission
from .throttling import WompiWebhookRateThrottle

logger = logging.getLogger(__name__)


class CarritoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        carrito = services.obtener_o_crear_carrito(request.user)
        return Response(serializers.CarritoCompraSerializer(carrito).data)


class ProductoCarritoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = serializers.ProductoCarritoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = services.agregar_producto_carrito(
                usuario=request.user,
                producto_id=serializer.validated_data["producto"].id,
                cantidad=serializer.validated_data["cantidad"],
            )
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            serializers.ProductoCarritoSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request, producto_id):
        try:
            cantidad = int(request.data.get("cantidad", 0))
        except (TypeError, ValueError):
            return Response(
                {"detail": "cantidad debe ser un entero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            item = services.actualizar_cantidad_carrito(
                request.user, producto_id, cantidad
            )
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.ProductoCarritoSerializer(item).data)

    def delete(self, request, producto_id):
        try:
            services.eliminar_producto_carrito(request.user, producto_id)
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = serializers.PedidoCheckoutSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vd = serializer.validated_data
        try:
            pedido = services.crear_pedido_desde_carrito(
                usuario=request.user,
                tipo_pago=vd["tipo_pago"],
                direccion_envio=vd["direccion_envio"],
                coordenadas_lat=vd.get("coordenadas_lat"),
                coordenadas_lng=vd.get("coordenadas_lng"),
            )
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                **serializers.PedidoSerializer(pedido).data,
                "mensaje": (
                    "Pedido registrado. Un administrador revisará su solicitud "
                    "y definirá el costo de envío antes de habilitar el pago."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class IniciarPagoPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pedido_id):
        try:
            datos_wompi = services.obtener_datos_pago_wompi(pedido_id, request.user)
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"wompi": datos_wompi})


class PedidoListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = PedidoPagination

    def get(self, request):
        pedidos = (
            models.Pedido.objects.filter(usuario=request.user)
            .exclude(estado_pedido=models.Pedido.EstadoPedido.CANCELADO)
            .prefetch_related("pedidoproducto_set__producto")
            .order_by("-fecha_creacion")
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(pedidos, request)
        data = serializers.PedidoSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class WompiWebhookView(APIView):
    permission_classes = [WompiWebhookPermission]
    throttle_classes = [WompiWebhookRateThrottle]

    def post(self, request):
        payload = request.data

        if not wompi.verificar_firma_webhook(payload):
            logger.warning("Webhook Wompi con firma inválida recibido.")
            return Response(
                {"detail": "Firma inválida."}, status=status.HTTP_401_UNAUTHORIZED
            )

        evento = payload.get("event")
        if evento != "transaction.updated":
            return Response(status=status.HTTP_200_OK)

        transaccion = payload.get("data", {}).get("transaction", {})
        id_transaccion = transaccion.get("id")
        estado_wompi = transaccion.get("status")
        referencia = transaccion.get("reference", "")
        monto_centavos = transaccion.get("amount_in_cents")

        pedido_id = wompi.pedido_id_desde_referencia(referencia)
        if pedido_id is None:
            logger.error("Referencia Wompi no reconocida.")
            return Response(status=status.HTTP_200_OK)

        try:
            pedido = models.Pedido.objects.get(pk=pedido_id)
        except models.Pedido.DoesNotExist:
            logger.error("Pedido #%s no encontrado para referencia Wompi.", pedido_id)
            return Response(status=status.HTTP_200_OK)

        if not wompi.referencia_pertenece_a_pedido(pedido, referencia):
            logger.warning(
                "Referencia Wompi no coincide con el pedido #%s.", pedido_id
            )
            return Response(status=status.HTTP_200_OK)

        try:
            if estado_wompi == wompi.ESTADO_APROBADO:
                if monto_centavos is None:
                    logger.error(
                        "Webhook sin amount_in_cents — pedido #%s", pedido_id
                    )
                    return Response(status=status.HTTP_200_OK)

                services.confirmar_pago_wompi(
                    pedido_id,
                    id_transaccion,
                    monto_centavos=monto_centavos,
                )
                logger.info(
                    "Pago aprobado — pedido #%s, transacción %s",
                    pedido_id,
                    id_transaccion,
                )
            elif estado_wompi in wompi.ESTADOS_RECHAZADO:
                services.rechazar_pago_wompi(pedido_id, id_transaccion)
                logger.info(
                    "Pago rechazado (%s) — pedido #%s",
                    estado_wompi,
                    pedido_id,
                )
            else:
                logger.debug(
                    "Estado intermedio '%s' ignorado — pedido #%s",
                    estado_wompi,
                    pedido_id,
                )
        except ValidationError as e:
            logger.error(
                "Error procesando webhook — pedido #%s: %s",
                pedido_id,
                e.message,
            )

        return Response(status=status.HTTP_200_OK)


class AdminPedidoListView(APIView):
    permission_classes = [IsAdministrador]
    pagination_class = PedidoPagination

    def get(self, request):
        qs = (
            models.Pedido.objects.select_related("usuario")
            .prefetch_related("pedidoproducto_set__producto")
            .order_by("-fecha_creacion")
        )
        usuario_id = request.query_params.get("usuario_id")
        if usuario_id:
            qs = qs.filter(usuario_id=usuario_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.PedidoAdminReadSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class PedidoPresencialView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request):
        serializer = serializers.PedidoAdminSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vd = serializer.validated_data

        items_servicio = [
            {"producto_id": item["producto"].id, "cantidad": item["cantidad"]}
            for item in vd["items"]
        ]

        try:
            pedido = services.crear_pedido_presencial(
                usuario=vd.get("usuario"),
                items=items_servicio,
                tipo_pago=vd["tipo_pago"],
                direccion_envio=vd.get("direccion_envio", ""),
                costo_envio=vd.get("costo_envio", Decimal("0.00")),
                coordenadas_lat=vd.get("coordenadas_lat"),
                coordenadas_lng=vd.get("coordenadas_lng"),
            )
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            serializers.PedidoAdminReadSerializer(pedido).data,
            status=status.HTTP_201_CREATED,
        )


class ConfirmarPagoManualView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request, pedido_id):
        try:
            pedido = services.confirmar_pago_manual(pedido_id)
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.PedidoAdminReadSerializer(pedido).data)


class AdminAprobarPedidoView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request, pedido_id):
        serializer = serializers.PedidoAprobarSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            pedido = services.aprobar_pedido_online(
                pedido_id,
                serializer.validated_data["costo_envio"],
            )
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.PedidoAdminReadSerializer(pedido).data)


class AdminCancelarPedidoView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request, pedido_id):
        try:
            pedido = services.cancelar_pedido_admin(pedido_id)
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.PedidoAdminReadSerializer(pedido).data)


class AdminActualizarEstadoPedidoView(APIView):
    permission_classes = [IsAdministrador]

    def patch(self, request, pedido_id):
        serializer = serializers.PedidoEstadoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            pedido = services.actualizar_estado_pedido(
                pedido_id,
                serializer.validated_data["estado_pedido"],
            )
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.PedidoAdminReadSerializer(pedido).data)


class AvanzarEstadoPedidoView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request, pedido_id):
        try:
            pedido = services.avanzar_estado_pedido(pedido_id)
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.PedidoAdminReadSerializer(pedido).data)
