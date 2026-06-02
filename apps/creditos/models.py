# models.py
from datetime import timedelta

from django.db import models
from django.utils import timezone


class Credito(models.Model):

    class EstadoCredito(models.TextChoices):
        ACTIVO = "activo", "Activo"
        PAGADO = "pagado", "Pagado"
        VENCIDO = "vencido", "Vencido"

    pedido = models.ForeignKey(
        "ventas.Pedido",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    usuario = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    cantidad_cuotas = models.SmallIntegerField()

    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    interes = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    valor_cuota = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    frecuencia_dias = models.PositiveSmallIntegerField(
        default=30,
        help_text="Días entre cada cuota. Ej: 30 = mensual, 15 = quincenal.",
    )
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    observaciones = models.TextField(blank=True)

    estado = models.CharField(
        max_length=10,
        choices=EstadoCredito.choices,
        default=EstadoCredito.ACTIVO,
    )
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "credito"

    def __str__(self):
        return f"Crédito #{self.id}"

    @property
    def puede_editar(self) -> bool:
        return timezone.now() <= self.fecha_inicio + timedelta(minutes=15)

    @property
    def esta_vencido(self) -> bool:
        return self.estado == self.EstadoCredito.VENCIDO or (
            self.estado == self.EstadoCredito.ACTIVO
            and self.fecha_fin is not None
            and timezone.now() > self.fecha_fin
        )


class CuotaCredito(models.Model):

    class EstadoCuota(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADA = "pagada", "Pagada"
        VENCIDA = "vencida", "Vencida"
        PARCIAL = "parcial", "Parcial"

    credito = models.ForeignKey(
        Credito,
        on_delete=models.PROTECT,
        related_name="cuotas",
    )
    numero_cuota = models.SmallIntegerField()
    fecha_vencimiento = models.DateTimeField()

    valor_cuota_original = models.DecimalField(max_digits=10, decimal_places=2)

    incremento_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    valor_cuota_final = models.DecimalField(max_digits=10, decimal_places=2)

    valor_pagado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    fecha_pago = models.DateTimeField(null=True, blank=True)

    fecha_ultimo_interes = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Marca hasta qué período se calculó el interés. "
            "Se inicializa con fecha_vencimiento y avanza período a período."
        ),
    )

    estado = models.CharField(
        max_length=10,
        choices=EstadoCuota.choices,
        default=EstadoCuota.PENDIENTE,
    )

    notificaciones_activas = models.BooleanField(
        default=True,
        help_text="Si False, no se generan notificaciones para esta cuota.",
    )

    class Meta:
        db_table = "cuota_credito"
        ordering = ["numero_cuota"]

    def __str__(self):
        return f"Cuota #{self.numero_cuota} - Crédito #{self.credito_id}"

    @property
    def saldo_pendiente(self):
        return self.valor_cuota_final - self.valor_pagado
