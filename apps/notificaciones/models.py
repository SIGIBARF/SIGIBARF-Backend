from django.db import models


class Notificacion(models.Model):

    class TipoNotificacion(models.TextChoices):
        STOCK_PRODUCTO = "stock_producto", "Stock Producto"
        STOCK_INGREDIENTE = "stock_ingrediente", "Stock Ingrediente"
        VENCIMIENTO_PRODUCTO = "vencimiento_producto", "Vencimiento Producto"
        DEUDA_VENCIDA = "deuda_vencida", "Deuda Vencida"
        DEUDA_PROXIMA = "deuda_proxima", "Deuda Próxima"

    usuario = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    producto = models.ForeignKey(
        "inventario.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    ingrediente = models.ForeignKey(
        "inventario.Ingrediente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    credito = models.ForeignKey(
        "creditos.Credito",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    cuota_credito = models.ForeignKey(
        "creditos.CuotaCredito",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    tipo = models.CharField(
        max_length=30,
        choices=TipoNotificacion.choices,
    )

    mensaje = models.TextField(blank=True)

    leida = models.BooleanField(default=False)

    fecha_generada = models.DateTimeField(auto_now_add=True)

    fecha_leida = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "notificacion"
        ordering = ["-fecha_generada"]

    @property
    def source_type(self):
        if self.producto_id: return "producto"
        if self.ingrediente_id: return "ingrediente"
        if self.credito_id: return "credito"
        if self.cuota_credito_id: return "cuota_credito"
        return None

    @property
    def source_id(self):
        if self.producto_id: return self.producto_id
        if self.ingrediente_id: return self.ingrediente_id
        if self.credito_id: return self.credito_id
        if self.cuota_credito_id: return self.cuota_credito_id
        return None

    def clean(self):
        from django.core.exceptions import ValidationError
        fks = [self.producto_id, self.ingrediente_id, self.credito_id, self.cuota_credito_id]
        if sum(x is not None for x in fks) > 1:
            raise ValidationError("Solo se puede asignar una referencia (producto, ingrediente, credito o cuota_credito) a la vez.")

    def resolve(self):
        from django.utils import timezone
        self.leida = True
        self.fecha_leida = timezone.now()
        self.save(update_fields=['leida', 'fecha_leida'])

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.usuario}"
