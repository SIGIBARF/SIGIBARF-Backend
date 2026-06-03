# serializers.py
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.ventas.models import Pedido

from .models import Credito, CuotaCredito


class CreditoDetailSerializer(serializers.ModelSerializer):
    pedido_id = serializers.PrimaryKeyRelatedField(source="pedido", read_only=True)
    usuario_id = serializers.PrimaryKeyRelatedField(source="usuario", read_only=True)
    saldo = serializers.SerializerMethodField()

    class Meta:
        model = Credito
        fields = [
            "id",
            "pedido_id",
            "usuario_id",
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
                "La cantidad de cuotas debe ser mayor a 0."
            )
        return value

    def validate_frecuencia_dias(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "La frecuencia de días debe ser al menos 1."
            )
        return value

    def validate_pedido_id(self, pedido):
        if not pedido.cliente_presencial:
            raise serializers.ValidationError(
                "Solo se puede asociar crédito a pedidos presenciales."
            )
        if pedido.tipo_pago != Pedido.TipoPago.CREDITO:
            raise serializers.ValidationError(
                'El pedido debe tener tipo de pago "credito".'
            )
        if pedido.estado_pago == Pedido.EstadoPago.APROBADO:
            raise serializers.ValidationError(
                "El pedido ya está confirmado y no admite un nuevo crédito."
            )
        if Credito.objects.filter(
            pedido=pedido, fecha_eliminacion__isnull=True
        ).exists():
            raise serializers.ValidationError(
                "Este pedido ya tiene un crédito activo asociado."
            )
        return pedido

    def validate_interes(self, value):
        if value < 0:
            raise serializers.ValidationError("El interés no puede ser negativo.")
        if value > 1:
            raise serializers.ValidationError(
                "El interés debe expresarse en decimal (ej. 0.05 para 5 %)."
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
        min_value="0.01",
    )

    def validate_monto(self, value):
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a 0.")
        return value
