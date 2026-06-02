from django.core.exceptions import ValidationError
from django.db import transaction

from . import models


def registrar_salida_producto(producto, cantidad, comentarios=""):
    if cantidad < 1:
        raise ValidationError("La cantidad debe ser al menos 1.")

    with transaction.atomic():
        producto_bloqueado = models.Producto.objects.select_for_update().get(
            pk=producto.pk
        )

        if producto_bloqueado.stock_actual < cantidad:
            raise ValidationError(
                f'Stock insuficiente para "{producto_bloqueado.nombre}". '
                f"Disponible: {producto_bloqueado.stock_actual}, solicitado: {cantidad}."
            )

        stock_anterior = producto_bloqueado.stock_actual
        producto_bloqueado.stock_actual = stock_anterior - cantidad
        producto_bloqueado.save(update_fields=["stock_actual"])

        movimiento = models.MovimientoProducto.objects.create(
            id_producto=producto_bloqueado,
            tipo_movimiento="SALIDA",
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_posterior=producto_bloqueado.stock_actual,
            comentarios=comentarios,
        )

    return movimiento


def registrar_entrada_producto(producto, cantidad, comentarios=""):
    stock_anterior = producto.stock_actual
    stock_posterior = stock_anterior + cantidad

    producto.stock_actual = stock_posterior
    producto.save()

    models.MovimientoProducto.objects.create(
        id_producto=producto,
        tipo_movimiento="ENTRADA",
        cantidad=cantidad,
        stock_anterior=stock_anterior,
        stock_posterior=stock_posterior,
        comentarios=comentarios,
    )


def registrar_ajuste_producto(producto, cantidad_nueva, comentarios=""):
    stock_anterior = producto.stock_actual

    producto.stock_actual = cantidad_nueva
    producto.save()

    models.MovimientoProducto.objects.create(
        id_producto=producto,
        tipo_movimiento="AJUSTE",
        cantidad=cantidad_nueva,
        stock_anterior=stock_anterior,
        stock_posterior=cantidad_nueva,
        comentarios=comentarios,
    )


def crear_produccion(id_producto, cantidad_producida, fecha_vencimiento):
    if cantidad_producida <= 0:
        raise ValidationError("cantidad_producida debe ser mayor que 0")
    if fecha_vencimiento is None:
        raise ValidationError("fecha_vencimiento es requerida")

    with transaction.atomic():
        # traer el producto (select for update para que no se edite el producto durante la produccion)
        producto = models.Producto.objects.select_for_update().get(pk=id_producto)

        # traer ingredientes del producto
        relacion_ings = models.ProductoIngrediente.objects.select_related(
            "id_ingrediente"
        ).filter(id_producto=id_producto)

        validar_stock_produccion(relacion_ings, cantidad_producida)

        # descontar ingredientes y crear movimientos
        for rel in relacion_ings:
            ingrediente = models.Ingrediente.objects.select_for_update().get(
                pk=rel.id_ingrediente.id
            )
            stock_anterior = ingrediente.stock_actual
            ingrediente.stock_actual = (
                stock_anterior - rel.cantidad_ingrediente * cantidad_producida
            )
            ingrediente.save()

            models.MovimientoIngrediente.objects.create(
                id_ingrediente=ingrediente,
                tipo_movimiento="SALIDA",
                stock_anterior=stock_anterior,
                stock_posterior=ingrediente.stock_actual,
                cantidad=rel.cantidad_ingrediente * cantidad_producida,
                comentarios="Movimiento de salida generado por producción.",
            )

        # aumentar stock del producto y crear movimiento producto
        stock_anterior_prod = producto.stock_actual
        producto.stock_actual = stock_anterior_prod + cantidad_producida
        producto.save()

        models.MovimientoProducto.objects.create(
            id_producto=producto,
            tipo_movimiento="ENTRADA",
            stock_anterior=stock_anterior_prod,
            stock_posterior=producto.stock_actual,
            cantidad=cantidad_producida,
            comentarios="Movimiento de entrada generado por producción.",
        )

        # crear registro de produccion
        produccion = models.Produccion.objects.create(
            id_producto=producto,
            cantidad_producida=cantidad_producida,
            fecha_vencimiento=fecha_vencimiento,
        )

        return produccion


def validar_stock_produccion(relacion_ings, cantidad_producida):
    insuficientes = []
    for rel in relacion_ings:
        requerido = rel.cantidad_ingrediente * cantidad_producida
        if rel.id_ingrediente.stock_actual < requerido:
            insuficientes.append((rel.id_ingrediente, requerido))

    if insuficientes:
        ing, req = insuficientes[0]
        raise ValidationError(
            f'Ingrediente "{ing.nombre}" (id={ing.id}) no tiene stock suficiente: requerido {req}, disponible {ing.stock_actual}'
        )
