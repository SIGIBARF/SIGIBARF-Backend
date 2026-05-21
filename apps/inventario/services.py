import math
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

import models


def crear_produccion(id_producto, cantidad_producida):
    if cantidad_producida <= 0:
        raise ValidationError('cantidad_producida debe ser mayor que 0')

    with transaction.atomic():
        # Lock producto row
        producto = models.Producto.objects.select_for_update().get(pk=id_producto)

        # traer ingredientes del producto
        relacion_ings = models.ProductoIngrediente.objects.select_related('id_ingrediente').filter(id_producto=producto)

        # calcular requerimientos por ingrediente
        requeridos = []  # tuples (ingrediente, requerido_int, porcentaje_decimal)
        for rel in relacion_ings:
            porcentaje = Decimal(rel.porcentaje_ingrediente)
            # cantidad requerida = porcentaje (%) * cantidad_producida
            req_decimal = (porcentaje / Decimal('100')) * Decimal(cantidad_producida)
            req_int = int(math.ceil(float(req_decimal)))
            requeridos.append((rel.id_ingrediente, req_int, porcentaje))

        # validar stock suficiente
        insuficientes = []
        for ingrediente, req_int, _ in requeridos:
            ingrediente = models.Ingrediente.objects.select_for_update().get(pk=ingrediente.pk)
            if ingrediente.stock_actual < req_int:
                insuficientes.append((ingrediente, req_int))

        if insuficientes:
            ing, req = insuficientes[0]
            raise ValidationError(f'Ingrediente "{ing.nombre}" (id={ing.id}) no tiene stock suficiente: requerido {req}, disponible {ing.stock_actual}')

        # descontar ingredientes y crear movimientos
        movimientos_ingrediente = []
        for ingrediente, req_int, _ in requeridos:
            ingrediente = models.Ingrediente.objects.select_for_update().get(pk=ingrediente.pk)
            stock_anterior = ingrediente.stock_actual
            ingrediente.stock_actual = stock_anterior - req_int
            ingrediente.save()

            mov = models.MovimientoIngrediente.objects.create(
                id_ingrediente=ingrediente,
                tipo_movimiento='SALIDA',
                stock_anterior=stock_anterior,
                stock_posterior=ingrediente.stock_actual,
                cantidad=req_int,
            )
            movimientos_ingrediente.append(mov)

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
        )

        # crear registro de produccion
        produccion = models.Produccion.objects.create(
            id_producto=producto,
            cantidad_producida=cantidad_producida,
        )

        return produccion
