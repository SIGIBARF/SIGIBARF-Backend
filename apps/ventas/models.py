from django.db import models
from django.db.models import Q


class CarritoCompra(models.Model):

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        CHECKOUT = "checkout", "Checkout"
        COMPLETADO = "completado", "Completado"
        ABANDONADO = "abandonado", "Abandonado"

    usuario = models.OneToOneField(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        help_text="Usuario/Cliente al que pertenece el carrito",
    )

    estado = models.CharField(
        max_length=15,
        choices=Estado.choices,
        default=Estado.ACTIVO,
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
        TARJETA = "tarjeta", "Tarjeta"
        TRANSFERENCIA = "transferencia", "Transferencia"
        BILLETERA_DIGITAL = "billetera_digital", "Billetera_digital"
        EFECTIVO = "efectivo", "Efectivo"  # Solo en caso de ser presencial
        CREDITO = "credito", "Credito"  # Solo en caso de ser presencial

    class EstadoPedido(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        CONFIRMADO = "confirmado", "Confirmado"
        PREPARANDO = "preparando", "Preparando"
        ENVIADO = "enviado", "Enviado"
        ENTREGADO = "entregado", "Entregado"
        CANCELADO = "cancelado", "Cancelado"

    class EstadoPago(models.TextChoices):
        APROBADO = "aprobado", "Aprobado"
        PENDIENTE = "pendiente", "Pendiente"
        RECHAZADO = "rechazado", "Rechazado"

    usuario = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        null=True,  # En caso de ser presencial
        blank=True,
    )
    tipo_pago = models.CharField(max_length=20, choices=TipoPago.choices)
    cliente_presencial = models.BooleanField(default=False)
    coordenadas_lat = models.FloatField(null=True, blank=True)
    coordenadas_lng = models.FloatField(null=True, blank=True)
    direccion_envio = models.TextField(null=True, blank=True)
    estado_pedido = models.CharField(
        max_length=20,
        choices=EstadoPedido.choices,
        default=EstadoPedido.PENDIENTE,
    )
    costo_envio = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    aprobado_admin = models.BooleanField(
        default=False,
        help_text=(
            "True cuando el administrador revisó el pedido y definió el envío. "
            "Requerido para habilitar el pago online."
        ),
    )
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
                condition=~Q(tipo_pago__in=["efectivo", "credito"])
                | Q(cliente_presencial=True),
                name="pago_presencial_requerido",
            ),
            models.CheckConstraint(
                condition=Q(precio_total__gt=0),
                name="precio_total_positivo",
            ),
            models.CheckConstraint(
                condition=Q(costo_envio__gte=0),
                name="costo_envio_no_negativo",
            ),
        ]

    def __str__(self):
        return f"Pedido {self.id} - Usuario {self.usuario_id}"


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
