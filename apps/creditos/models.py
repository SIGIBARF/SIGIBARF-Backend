from django.db import models


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

    valor_cuota = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    fecha_inicio = models.DateTimeField(auto_now_add=True)

    observaciones = models.TextField(blank=True)

    estado = models.CharField(
        max_length=10,
        choices=EstadoCredito.choices,
        default=EstadoCredito.ACTIVO,
    )

    fecha_eliminacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "credito"

    def __str__(self):
        return f"Crédito #{self.id}"


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

    valor_cuota_original = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    incremento_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    valor_cuota_final = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    valor_pagado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    fecha_pago = models.DateTimeField(
        null=True,
        blank=True,
    )

    estado = models.CharField(
        max_length=10,
        choices=EstadoCuota.choices,
        default=EstadoCuota.PENDIENTE,
    )

    class Meta:
        db_table = "cuota_credito"

    def __str__(self):
        return f"Cuota #{self.numero_cuota} - Crédito #{self.credito_id}"
