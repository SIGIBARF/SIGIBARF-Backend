from django.db import models

class CarritoDeCompras(models.Model):
    # Relación intermedia entre Cliente y Producto
    cliente = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, help_text="Usuario/Cliente al que pertenece el carrito")
    producto_id = models.IntegerField(help_text="ID del producto (Reemplazar con ForeignKey a inventario.Producto cuando exista)")
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'carrito_de_compras'
        verbose_name = 'Carrito de Compras'
        verbose_name_plural = 'Carritos de Compras'

    def __str__(self):
        return f"Carrito Cliente {self.cliente.id} - Producto {self.producto_id}"


class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Procesando', 'Procesando'),
        ('Enviado', 'Enviado'),
        ('Entregado', 'Entregado'),
        ('Cancelado', 'Cancelado'),
    ]

    FORMA_PAGO_CHOICES = [
        ('Efectivo', 'Efectivo'),
        ('Tarjeta', 'Tarjeta'),
        ('Transferencia', 'Transferencia'),
    ]

    ESTADO_PAGO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Pagado', 'Pagado'),
        ('Rechazado', 'Rechazado'),
    ]

    cliente = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, help_text="Usuario/Cliente que realiza el pedido")
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES)
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='Pendiente')
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'pedido'
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'

    def __str__(self):
        return f"Pedido {self.id} - Cliente {self.cliente.id}"


class PedidoProducto(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='productos')
    producto_id = models.IntegerField(help_text="ID del producto (Reemplazar con ForeignKey a inventario.Producto cuando exista)")
    cantidad = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'pedido_producto'
        verbose_name = 'Pedido Producto'
        verbose_name_plural = 'Pedidos Productos'

    def __str__(self):
        return f"Pedido {self.pedido.id} - Producto {self.producto_id}"
