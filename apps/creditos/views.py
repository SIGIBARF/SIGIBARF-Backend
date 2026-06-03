# views.py
from datetime import timedelta

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.usuarios.permissions import IsAdministrador

from .models import Credito, CuotaCredito
from .notificaciones import (
    check_credito_notifications,
    check_cuota_notifications,
)
from .serializers import (CreditoDetailSerializer, CreditoUpdateSerializer,
                          CuotaCreditoDetailSerializer,
                          CuotaCreditoListSerializer,
                          CuotaCreditoToggleNotificacionesSerializer,
                          RegistrarPagoSerializer)
from .services import registrar_mayor_monto


class CreditoViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAdministrador]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            Credito.objects.filter(fecha_eliminacion__isnull=True)
            .select_related("pedido", "usuario")
            .prefetch_related("cuotas")
        )

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return CreditoUpdateSerializer
        return CreditoDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        check_credito_notifications(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        credito = self.get_object()

        if not credito.puede_editar:
            return Response(
                {
                    "error": (
                        "No se puede eliminar un crédito después de "
                        "15 minutos de su creación."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        credito.fecha_eliminacion = timezone.now()
        credito.save(update_fields=["fecha_eliminacion"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="registrar-pago")
    def registrar_pago(self, request, pk=None):
        credito = self.get_object()

        serializer = RegistrarPagoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        monto = serializer.validated_data["monto"]

        try:
            resultado = registrar_mayor_monto(credito, monto)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        credito.refresh_from_db()
        resultado["estado_credito"] = credito.estado

        return Response(resultado, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="cuotas")
    def cuotas(self, request, pk=None):
        credito = self.get_object()
        cuotas = credito.cuotas.all().order_by("numero_cuota")

        for cuota in cuotas.exclude(estado=CuotaCredito.EstadoCuota.PAGADA):
            check_cuota_notifications(cuota)

        serializer = CuotaCreditoDetailSerializer(cuotas, many=True)
        return Response(serializer.data)


class CuotaCreditoViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = [IsAdministrador]

    def get_queryset(self):
        qs = CuotaCredito.objects.select_related("credito").filter(
            credito__fecha_eliminacion__isnull=True
        )
        credito_id = self.request.query_params.get("credito")
        if credito_id:
            qs = qs.filter(credito_id=credito_id)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return CuotaCreditoListSerializer
        return CuotaCreditoDetailSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        for cuota in queryset.exclude(estado=CuotaCredito.EstadoCuota.PAGADA):
            check_cuota_notifications(cuota)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        check_cuota_notifications(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["patch"],
        url_path="toggle-notificaciones",
        serializer_class=CuotaCreditoToggleNotificacionesSerializer,
    )
    def toggle_notificaciones(self, request, pk=None):
        cuota = self.get_object()

        if cuota.estado == CuotaCredito.EstadoCuota.PAGADA:
            return Response(
                {
                    "error": (
                        "No se pueden modificar las notificaciones de una cuota "
                        "que ya está pagada."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if cuota.credito.fecha_eliminacion is not None:
            return Response(
                {"error": "El crédito asociado a esta cuota ha sido eliminado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "notificaciones_activas" in request.data:
            serializer = CuotaCreditoToggleNotificacionesSerializer(
                cuota, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            cuota.notificaciones_activas = not cuota.notificaciones_activas
            cuota.save(update_fields=["notificaciones_activas"])

        return Response(
            {
                "cuota": cuota.numero_cuota,
                "notificaciones_activas": cuota.notificaciones_activas,
            },
            status=status.HTTP_200_OK,
        )
