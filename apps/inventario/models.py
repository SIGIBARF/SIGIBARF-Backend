from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


UNIDADES = [
    ('kg', 'kg'),
    ('g', 'g'),
    ('l', 'l'),
    ('ml', 'ml'),
]


TIPO_MOVIMIENTO_CHOICES = [
    ('ENTRADA', 'ENTRADA'),
    ('SALIDA', 'SALIDA'),
    ('AJUSTE', 'AJUSTE'),
]


class Ingrediente(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    proveedor = models.CharField(max_length=100)
    stock_actual = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    stock_minimo = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    unidad_medida = models.CharField(max_length=3, choices=UNIDADES)
    
    class Meta:
        db_table = 'ingrediente'
        verbose_name = 'Ingrediente'
        verbose_name_plural = 'Ingredientes'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.unidad_medida})"


class Producto(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    stock_actual = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    stock_minimo = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    inhabilitado = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'producto'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class ProductoIngrediente(models.Model):
    id = models.AutoField(primary_key=True)
    id_producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='ingredientes')
    id_ingrediente = models.ForeignKey(Ingrediente, on_delete=models.CASCADE)
    porcentaje_ingrediente = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    
    class Meta:
        db_table = 'producto_ingrediente'
        verbose_name = 'Producto_Ingrediente'
        verbose_name_plural = 'Productos_Ingredientes'
        ordering = ['id']

    def __str__(self):
        return f"{self.id_producto} - {self.id_ingrediente} : {self.porcentaje_ingrediente}%"


class Produccion(models.Model):
    id = models.AutoField(primary_key=True)
    id_producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad_producida = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'produccion'
        verbose_name = 'Produccion'
        verbose_name_plural = 'Producciones'
        ordering = ['id']

    def __str__(self):
        return f"Produccion {self.id} - {self.id_producto} x {self.cantidad_producida}"


class MovimientoIngrediente(models.Model):
    id = models.AutoField(primary_key=True)
    id_ingrediente = models.ForeignKey(Ingrediente, on_delete=models.PROTECT)
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO_CHOICES)
    stock_anterior = models.PositiveIntegerField()
    stock_posterior = models.PositiveIntegerField()
    cantidad = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    comentarios = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'movimiento_ingrediente'
        verbose_name = 'Movimiento_Ingrediente'
        verbose_name_plural = 'Movimientos_Ingredientes'
        ordering = ['fecha']

    def __str__(self):
        return f"MI {self.id_ingrediente} {self.tipo_movimiento} {self.cantidad}"


class MovimientoProducto(models.Model):
    id = models.AutoField(primary_key=True)
    id_producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO_CHOICES)
    stock_anterior = models.PositiveIntegerField()
    stock_posterior = models.PositiveIntegerField()
    cantidad = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    comentarios = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'movimiento_producto'
        verbose_name = 'Movimiento_Producto'
        verbose_name_plural = 'Movimientos_Productos'
        ordering = ['fecha']

    def __str__(self):
        return f"MP {self.id_producto} {self.tipo_movimiento} {self.cantidad}"
