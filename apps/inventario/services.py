import math
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from . import models


def crear_produccion(id_producto, cantidad_producida):
    if cantidad_producida <= 0:
        raise ValidationError('cantidad_producida debe ser mayor que 0')

    with transaction.atomic():
        # traer el producto (select for update para que no se edite el producto durante la produccion)
        producto = models.Producto.objects.select_for_update().get(pk=id_producto)

        # traer ingredientes del producto
        relacion_ings = models.ProductoIngrediente.objects.select_related('id_ingrediente').filter(id_producto=producto)

        # validar stock suficiente
        insuficientes = []
        for rel in relacion_ings:
            if rel.id_ingrediente.stock_actual < rel.cantidad_ingrediente*cantidad_producida:
                insuficientes.append((rel.id_ingrediente, rel.cantidad_ingrediente*cantidad_producida))

        if insuficientes:
            ing, req = insuficientes[0]
            raise ValidationError(f'Ingrediente "{ing.nombre}" (id={ing.id}) no tiene stock suficiente: requerido {req}, disponible {ing.stock_actual}')

        # descontar ingredientes y crear movimientos
        for rel in relacion_ings:
            ingrediente = models.Ingrediente.objects.select_for_update().get(pk=rel.id_ingrediente.id)
            stock_anterior = ingrediente.stock_actual
            ingrediente.stock_actual = stock_anterior - rel.cantidad_ingrediente*cantidad_producida
            ingrediente.save()

            mov = models.MovimientoIngrediente.objects.create(
                id_ingrediente=ingrediente,
                tipo_movimiento='SALIDA',
                stock_anterior=stock_anterior,
                stock_posterior=ingrediente.stock_actual,
                cantidad=rel.cantidad_ingrediente*cantidad_producida,
                comentarios="Movimiento de salida generado por producción.",
            )

        # aumentar stock del producto y crear movimiento producto
        stock_anterior_prod = producto.stock_actual
        producto.stock_actual = stock_anterior_prod + cantidad_producida
        producto.save()

        movimiento_producto = models.MovimientoProducto.objects.create(
            id_producto=producto,
            tipo_movimiento='ENTRADA',
            stock_anterior=stock_anterior_prod,
            stock_posterior=producto.stock_actual,
            cantidad=cantidad_producida,
            comentarios="Movimiento de entrada generado por producción."
        )

        # crear registro de produccion
        produccion = models.Produccion.objects.create(
            id_producto=producto,
            cantidad_producida=cantidad_producida,
        )

        return produccion