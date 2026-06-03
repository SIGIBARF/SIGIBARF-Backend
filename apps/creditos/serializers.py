# serializers.py
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.ventas.models import Pedido

from .models import Credito, CuotaCredito


class CreditoDetailSerializer(serializers.ModelSerializer):
    pedido_id = serializers.PrimaryKeyRelatedField(source="pedido", read_only=True)
    usuario_id = serializers.PrimaryKeyRelatedField(source="usuario", read_only=True)
    saldo = serializers.SerializerMethodField()
    usuario = serializers.SerializerMethodField()

    class Meta:
        model = Credito
        fields = [
            "id",
            "pedido_id",
            "usuario_id",
            "usuario",
            "cantidad_cuotas",
            "valor_total",
            "valor_cuota",
            "interes",
            "frecuencia_dias",
            "fecha_inicio",
            "fecha_fin",
            "observaciones",
            "estado",
            "saldo",
        ]
        read_only_fields = fields

    def get_saldo(self, obj):
        return obj.saldo

    def get_usuario(self, obj):
        if obj.usuario:
            return f"{obj.usuario.nombre} {obj.usuario.apellido}"
        return None


class CreditoCreateSerializer(serializers.ModelSerializer):
    User = get_user_model()

    pedido_id = serializers.PrimaryKeyRelatedField(
        source="pedido", queryset=Pedido.objects.all()
    )
    usuario_id = serializers.PrimaryKeyRelatedField(
        source="usuario", queryset=User.objects.all()
    )

    valor_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    valor_cuota = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    interes = serializers.DecimalField(
        required=False, default=0.0, max_digits=5, decimal_places=2
    )

    class Meta:
        model = Credito
        fields = [
            "usuario_id",
            "pedido_id",
            "cantidad_cuotas",
            "interes",
            "frecuencia_dias",
            "valor_total",
            "valor_cuota",
            "observaciones",
        ]

    def validate_cantidad_cuotas(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "La cantidad de cuotas debe ser al menos 1. Recibido: {}.".format(value)
            )
        return value

    def validate_frecuencia_dias(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "La frecuencia de pago debe ser al menos 1 día. Recibido: {}.".format(value)
            )
        return value

    def validate_pedido_id(self, pedido):
        if not pedido.cliente_presencial:
            raise serializers.ValidationError(
                f"No se puede crear crédito: el pedido #{pedido.id} es de venta en línea. "
                "Solo se permiten créditos para pedidos presenciales."
            )
        if pedido.tipo_pago != Pedido.TipoPago.CREDITO:
            raise serializers.ValidationError(
                f"No se puede crear crédito: el pedido #{pedido.id} tiene tipo de pago "
                f"'{pedido.get_tipo_pago_display()}'. Debe ser 'Credito'."
            )
        if pedido.estado_pago == Pedido.EstadoPago.APROBADO:
            raise serializers.ValidationError(
                f"No se puede crear crédito: el pedido #{pedido.id} ya está confirmado "
                "y pagado. No se puede modificar."
            )
        if Credito.objects.filter(
            pedido=pedido, fecha_eliminacion__isnull=True
        ).exists():
            raise serializers.ValidationError(
                f"No se puede crear crédito: el pedido #{pedido.id} ya tiene un plan "
                "de financiación activo. Elimine el crédito anterior si desea crear uno nuevo."
            )
        return pedido

    def validate_interes(self, value):
        if value < 0:
            raise serializers.ValidationError(
                f"El interés no puede ser negativo. Recibido: {value}. "
                "Exprese como decimal (ej. 0.05 para 5%)."
            )
        if value > 1:
            raise serializers.ValidationError(
                f"El interés debe ser menor o igual a 1 (100%). Recibido: {value}. "
                "Exprese como decimal (ej. 0.05 para 5%)."
            )
        return value


class CreditoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credito
        fields = ["observaciones"]


class CuotaCreditoDetailSerializer(serializers.ModelSerializer):
    credito_id = serializers.PrimaryKeyRelatedField(source="credito", read_only=True)

    class Meta:
        model = CuotaCredito
        fields = [
            "id",
            "credito_id",
            "numero_cuota",
            "fecha_vencimiento",
            "valor_cuota_original",
            "incremento_anterior",
            "valor_cuota_final",
            "valor_pagado",
            "fecha_pago",
            "estado",
            "notificaciones_activas",
        ]
        read_only_fields = fields


class CuotaCreditoListSerializer(serializers.ModelSerializer):
    credito_id = serializers.PrimaryKeyRelatedField(source="credito", read_only=True)

    class Meta:
        model = CuotaCredito
        fields = [
            "id",
            "credito_id",
            "numero_cuota",
            "fecha_vencimiento",
            "valor_cuota_original",
            "incremento_anterior",
            "valor_cuota_final",
            "valor_pagado",
            "fecha_pago",
            "estado",
            "notificaciones_activas",
        ]
        read_only_fields = fields


class CuotaCreditoToggleNotificacionesSerializer(serializers.ModelSerializer):

    class Meta:
        model = CuotaCredito
        fields = ["notificaciones_activas"]


class CuotaCreditoObservacionCreditoSerializer(serializers.ModelSerializer):

    class Meta:
        model = Credito
        fields = ["observaciones"]


class RegistrarPagoSerializer(serializers.Serializer):

    monto = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    def validate_monto(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                f"El monto a pagar debe ser mayor a $0. Recibido: ${value}."
            )
        return value
