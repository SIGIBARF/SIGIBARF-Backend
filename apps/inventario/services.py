from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone

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
        
    if fecha_vencimiento.date() < timezone.localdate():
        raise ValidationError("La fecha de vencimiento no puede ser anterior a la fecha actual.")

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


def registrar_receta_en_bloque(ingredientes_data):
    total_porcentaje = sum(Decimal(str(item["porcentaje_ingrediente"])) for item in ingredientes_data)
    if total_porcentaje != Decimal("100"):
        raise ValidationError(f"La suma de los porcentajes debe ser exactamente 100%. Valor actual: {total_porcentaje}%.")
    
    id_productos = set(item["id_producto"].id for item in ingredientes_data)
    if len(id_productos) > 1:
        raise ValidationError("Todos los ingredientes deben pertenecer al mismo producto.")
    
    id_producto = id_productos.pop() if id_productos else None

    with transaction.atomic():
        if id_producto:
            models.ProductoIngrediente.objects.filter(id_producto=id_producto).delete()
            
        registros = [
            models.ProductoIngrediente(**item)
            for item in ingredientes_data
        ]
        return models.ProductoIngrediente.objects.bulk_create(registros)


def agregar_ingrediente_receta(ingrediente_data):
    producto = ingrediente_data["id_producto"]
    nuevo_porcentaje = Decimal(str(ingrediente_data["porcentaje_ingrediente"]))
    
    qs = models.ProductoIngrediente.objects.filter(id_producto=producto)
    total_actual = qs.aggregate(total=Sum("porcentaje_ingrediente"))["total"] or Decimal("0")
    
    if total_actual >= Decimal("100"):
        raise ValidationError("El producto ya tiene una receta completa (100%).")
    
    if total_actual + nuevo_porcentaje > Decimal("100"):
        raise ValidationError(f"Superaría el 100%. Actual: {total_actual}%, Nuevo: {nuevo_porcentaje}%.")
        
    return models.ProductoIngrediente.objects.create(**ingrediente_data)


def actualizar_ingrediente_receta(instancia, ingrediente_data):
    producto = ingrediente_data.get("id_producto", instancia.id_producto)
    nuevo_porcentaje = Decimal(str(ingrediente_data.get("porcentaje_ingrediente", instancia.porcentaje_ingrediente)))
    
    qs = models.ProductoIngrediente.objects.filter(id_producto=producto).exclude(pk=instancia.pk)
    total_sin_esta_fila = qs.aggregate(total=Sum("porcentaje_ingrediente"))["total"] or Decimal("0")
    
    if total_sin_esta_fila + nuevo_porcentaje > Decimal("100"):
        raise ValidationError(f"Este cambio superaría el 100%. Otros ingredientes: {total_sin_esta_fila}%, Nuevo: {nuevo_porcentaje}%.")
        
    for key, value in ingrediente_data.items():
        setattr(instancia, key, value)
    instancia.save()
    return instancia

