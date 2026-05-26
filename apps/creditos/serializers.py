from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from ventas.models import Pedido

from .models import Credito, CuotaCredito


# GET credito unico y lista
class CreditoDetailSerializer(serializers.ModelSerializer):
    User = get_user_model()
    pedido_id = serializers.PrimaryKeyRelatedField(
        source="pedido", queryset=Pedido.objects.all()
    )
    usuario_id = serializers.PrimaryKeyRelatedField(
        source="usuario", queryset=User.objects.all()
    )

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
            "fecha_inicio",
            "fecha_fin",
            "observaciones",
            "estado",
        ]
        read_only_fields = fields


# POST crear credito
class CreditoCreateSerializer(serializers.ModelSerializer):
    User = get_user_model()
    pedido_id = serializers.PrimaryKeyRelatedField(
        source="pedido", queryset=Pedido.objects.all()
    )
    usuario_id = serializers.PrimaryKeyRelatedField(
        source="usuario", queryset=User.objects.all()
    )
    valor_total = serializers.PositiveIntegerField(read_only=True)
    valor_cuota = serializers.PositiveIntegerField(read_only=True)

    class Meta:
        model = Credito
        fields = [
            "usuario_id",
            "pedido_id",
            "cantidad_cuotas",
            "interes",
            "fecha_inicio",
            "valor_total" "valor_cuota" "observaciones",
        ]

    def validate_cantidad_cuotas(self, value):
        if value < 1:
            raise serializers.ValidationError("Las cuotas no puede ser 0 o negativo")
        return value

    def validate_interes(self, value):
        if value < 0:
            raise serializers.ValidationError("El interes no puede ser negativo")
        return value

    def validate_fecha_inicio(self, value):
        ayer = timezone.now().date() - timedelta(days=1)
        if value < ayer:
            raise serializers.ValidationError(
                "La fecha de inicio no puede ser anterior a ayer."
            )
        return value

    def validate_pedido_id(self, pedido):
        if Credito.objects.filter(
            pedido=pedido, fecha_eliminacion__isnull=True
        ).exists():
            raise serializers.ValidationError(
                "Este pedido ya tiene un credito activo asociado"
            )


# PATCH actualizar observaciones credito
class CreditoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credito
        fields = ["observaciones"]


# GET cuota unica de credito
class CuotaCreditoDetailSerializer(serializers.ModelSerializer):
    credito_id = serializers.PrimaryKeyRelatedField(
        source="credito", queryset=Credito.objects.all()
    )

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
        ]
        read_only_fields = fields


# GET todas las coutas de un credito
class CuotaCreditoListSerializer(serializers.ModelSerializer):
    credito_id = serializers.PrimaryKeyRelatedField(
        source="credito", queryset=Credito.objects.all()
    )

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
        ]
        read_only_fields = fields


# PATCH registrar pago de cuota credito
class CuotaCreditoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuotaCredito
        fields = [
            "valor_pagado",
            "fecha_pago",
        ]

    def validate_valor_pagado(self, value):
        if value <= 0:
            raise serializers.ValidationError("El valor pagado no puede ser negativo.")
        return value

    def validate(self, data):
        fecha_pago = data.get("fecha_pago")
        cuotacredito = self.instance
        ya_pagada = cuotacredito.fecha_pago is not None

        if cuotacredito.credito in ["pagado"]:
            raise serializers.ValidationError(
                "No se puede registrar un pago en un crédito pagado."
            )

        if cuotacredito.fecha_pago is not None:
            raise serializers.ValidationError(
                "Esta cuota ya fue registrada como pagada"
            )

        ultima_cuota_pagada = (
            CuotaCredito.objects.filter(
                credito=cuotacredito.credito,
                fecha_pago__isnull=False,
                numero_cuota__lt=cuotacredito.numero_cuota,
            )
            .order_by("-fecha_pago")
            .first()
        )

        if ultima_cuota_pagada and fecha_pago:
            if fecha_pago < ultima_cuota_pagada.fecha_pago:
                raise serializers.ValidationError(
                    {
                        "fecha_pago": (
                            f"La fecha de pago no puede ser anterior al último pago registrado "
                            f"(Cuota #{ultima_cuota_pagada.numero_cuota} pagada el "
                            f"{ultima_cuota_pagada.fecha_pago.strftime('%d/%m/%Y')})"
                        )
                    }
                )
        if not ya_pagada:
            cuotas_pendientes_anteriores = CuotaCredito.objects.filter(
                credito=cuotacredito.credito,
                fecha_pago__isnull=True,
                numero_cuota__lt=cuotacredito.numero_cuota,
            ).exists()

            if cuotas_pendientes_anteriores:
                raise serializers.ValidationError(
                    "No se puede pagar esta cuota porque hay cuotas anteriores pendientes."
                )

        return data
