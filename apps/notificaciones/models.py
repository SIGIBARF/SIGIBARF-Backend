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
        "productos.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    ingrediente = models.ForeignKey(
        "productos.Ingrediente",
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

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.usuario}"
