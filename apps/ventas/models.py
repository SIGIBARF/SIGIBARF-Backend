from django.db import models
from django.db.models import Q


class CarritoCompra(models.Model):
    usuario = models.OneToOneField(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        help_text="Usuario/Cliente al que pertenece el carrito",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    fecha_actualizacion = models.DateTimeField(
        auto_now=True, verbose_name="Actualizado en"
    )

    class Meta:
        db_table = "carrito_compras"
        verbose_name = "Carrito de Compras"
        verbose_name_plural = "Carritos de Compras"

    def __str__(self):
        return f"Carrito {self.id} - Usuario {self.usuario_id}"


class ProductoCarrito(models.Model):
    producto = models.ForeignKey("inventario.Producto", on_delete=models.CASCADE)
    carrito_compra = models.ForeignKey(CarritoCompra, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "producto_carrito"
        verbose_name = "Producto carrito"
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "carrito_compra"],
                name="unique_producto_carrito",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gt=0),
                name="cantidad_positiva_carrito",
            ),
        ]

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} en carrito {self.carrito_compra_id}"


class Pedido(models.Model):
    class TipoPago(models.TextChoices):
        WOMPI = "wompi", "Wompi"
        EFECTIVO = "efectivo", "Efectivo"
        CREDITO = "credito", "Credito"

    class EstadoPago(models.TextChoices):
        APROBADO = "aprobado", "Aprobado"
        PENDIENTE = "pendiente", "Pendiente"
        RECHAZADO = "rechazado", "Rechazado"

    usuario = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    tipo_pago = models.CharField(
        max_length=20,
        choices=TipoPago.choices,
        null=True,
        blank=True,
        help_text="En pedidos web lo asigna el webhook de Wompi al aprobar.",
    )
    medio_pago = models.TextField(
        null=True,
        blank=True,
        help_text="Detalle del método reportado por Wompi (p. ej. CARD, NEQUI).",
    )
    cliente_presencial = models.BooleanField(default=False)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")

    referencia_wompi = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text="Referencia única enviada a Wompi (PEDIDO-{id}-{token}).",
    )
    id_transaccion_wompi = models.CharField(max_length=100, blank=True, null=True)
    estado_pago = models.CharField(
        max_length=20,
        choices=EstadoPago.choices,
        default=EstadoPago.PENDIENTE,
    )
    fecha_pago = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "pedido"
        verbose_name = "Pedido"
        constraints = [
            models.CheckConstraint(
                condition=Q(tipo_pago__isnull=True)
                | ~Q(tipo_pago__in=["efectivo", "credito"])
                | Q(cliente_presencial=True),
                name="pago_presencial_requerido",
            ),
            models.CheckConstraint(
                condition=Q(precio_total__gt=0),
                name="precio_total_positivo",
            ),
        ]

    def __str__(self):
        return f"Pedido {self.id} - Usuario {self.usuario_id}"

    @property
    def confirmado(self) -> bool:
        return self.estado_pago == self.EstadoPago.APROBADO


class PedidoProducto(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    producto = models.ForeignKey("inventario.Producto", on_delete=models.PROTECT)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "pedido_producto"
        verbose_name = "Pedido Producto"
        constraints = [
            models.UniqueConstraint(
                fields=["pedido", "producto"],
                name="unique_pedido_producto",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gt=0),
                name="cantidad_positiva_pedido",
            ),
            models.CheckConstraint(
                condition=Q(precio_unitario__gt=0),
                name="precio_unitario_positivo",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gt=0),
                name="subtotal_positivo",
            ),
        ]

    def __str__(self):
        return f"Pedido {self.pedido.id} - Producto {self.producto.id}"
