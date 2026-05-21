from django.contrib import admin
from . import models


@admin.register(models.Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'proveedor', 'stock_actual', 'stock_minimo', 'unidad_medida')


@admin.register(models.Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'precio', 'stock_actual', 'stock_minimo', 'inhabilitado')


@admin.register(models.ProductoIngrediente)
class ProductoIngredienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_producto', 'id_ingrediente', 'porcentaje_ingrediente')


@admin.register(models.Produccion)
class ProduccionAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_producto', 'cantidad_producida', 'fecha')


@admin.register(models.MovimientoIngrediente)
class MovimientoIngredienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_ingrediente', 'tipo_movimiento', 'cantidad', 'stock_anterior', 'stock_posterior', 'fecha')


@admin.register(models.MovimientoProducto)
class MovimientoProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_producto', 'tipo_movimiento', 'cantidad', 'stock_anterior', 'stock_posterior', 'fecha')
