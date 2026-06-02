from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventario import models as inventario_models
from apps.inventario import services as inventario_services

from . import models, wompi

TIPOS_PAGO_PRESENCIAL = frozenset(
    {
        models.Pedido.TipoPago.EFECTIVO,
        models.Pedido.TipoPago.CREDITO,
    }
)

_ESTADOS_PAGO_ABIERTO = frozenset(
    {
        models.Pedido.EstadoPago.PENDIENTE,
        models.Pedido.EstadoPago.RECHAZADO,
    }
)


def _bloquear_productos(producto_ids):
    ids_ordenados = sorted(set(producto_ids))
    return {
        p.pk: p
        for p in inventario_models.Producto.objects.select_for_update().filter(
            pk__in=ids_ordenados
        )
    }


def _construir_lineas(items_con_cantidad, productos_map):
    lineas = []

    for producto_id, cantidad in items_con_cantidad:
        producto = productos_map[producto_id]

        if producto.inhabilitado:
            raise ValidationError(
                f'El producto "{producto.nombre}" ya no está disponible.'
            )
        if producto.stock_actual < cantidad:
            raise ValidationError(
                f'Stock insuficiente para "{producto.nombre}". '
                f"Disponible: {producto.stock_actual}, requerido: {cantidad}."
            )

        subtotal = producto.precio * cantidad
        lineas.append(
            {
                "producto": producto,
                "cantidad": cantidad,
                "precio_unitario": producto.precio,
                "subtotal": subtotal,
            }
        )

    return lineas


def _subtotal_desde_lineas(lineas) -> Decimal:
    return sum((linea["subtotal"] for linea in lineas), Decimal("0.00"))


def _descontar_stock_pedido(pedido):
    lineas = list(pedido.pedidoproducto_set.select_related("producto"))
    productos_map = _bloquear_productos(linea.producto_id for linea in lineas)
    comentario = f"Salida por pedido #{pedido.id}"

    for linea in lineas:
        inventario_services.registrar_salida_producto(
            producto=productos_map[linea.producto_id],
            cantidad=linea.cantidad,
            comentarios=comentario,
        )


def _validar_pedido_editable(pedido):
    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError("El pedido ya está confirmado y no puede modificarse.")


def _pedido_web_abierto(usuario):
    return models.Pedido.objects.filter(
        usuario=usuario,
        cliente_presencial=False,
        estado_pago__in=_ESTADOS_PAGO_ABIERTO,
    ).exists()


def vaciar_carrito(usuario):
    try:
        carrito = models.CarritoCompra.objects.get(usuario=usuario)
    except models.CarritoCompra.DoesNotExist:
        return
    models.ProductoCarrito.objects.filter(carrito_compra=carrito).delete()


def obtener_o_crear_carrito(usuario):
    carrito, _ = models.CarritoCompra.objects.get_or_create(usuario=usuario)
    return carrito


def agregar_producto_carrito(usuario, producto_id, cantidad):
    if cantidad < 1:
        raise ValidationError("La cantidad debe ser al menos 1.")

    carrito = obtener_o_crear_carrito(usuario)

    try:
        producto = inventario_models.Producto.objects.get(
            pk=producto_id, inhabilitado=False
        )
    except inventario_models.Producto.DoesNotExist:
        raise ValidationError("Producto no encontrado o no disponible.")

    try:
        producto_carrito = models.ProductoCarrito.objects.get(
            carrito_compra=carrito, producto=producto
        )
        nueva_cantidad = producto_carrito.cantidad + cantidad
    except models.ProductoCarrito.DoesNotExist:
        producto_carrito = None
        nueva_cantidad = cantidad

    if producto.stock_actual < nueva_cantidad:
        raise ValidationError(
            f"Stock insuficiente. Disponible: {producto.stock_actual}."
        )

    if producto_carrito:
        producto_carrito.cantidad = nueva_cantidad
        producto_carrito.save()
    else:
        producto_carrito = models.ProductoCarrito.objects.create(
            carrito_compra=carrito,
            producto=producto,
            cantidad=nueva_cantidad,
        )

    return producto_carrito


def actualizar_cantidad_carrito(usuario, producto_id, cantidad):
    if cantidad < 1:
        raise ValidationError("La cantidad debe ser al menos 1.")

    try:
        producto_carrito = models.ProductoCarrito.objects.select_related(
            "producto"
        ).get(
            carrito_compra__usuario=usuario,
            producto_id=producto_id,
        )
    except models.ProductoCarrito.DoesNotExist:
        raise ValidationError("El producto no está en el carrito.")

    if producto_carrito.producto.stock_actual < cantidad:
        raise ValidationError(
            f"Stock insuficiente. "
            f"Disponible: {producto_carrito.producto.stock_actual}."
        )

    producto_carrito.cantidad = cantidad
    producto_carrito.save()
    return producto_carrito


def eliminar_producto_carrito(usuario, producto_id):
    eliminados, _ = models.ProductoCarrito.objects.filter(
        carrito_compra__usuario=usuario,
        producto_id=producto_id,
    ).delete()

    if eliminados == 0:
        raise ValidationError("El producto no estaba en el carrito.")


def _persistir_pedido(usuario, tipo_pago, cliente_presencial, lineas):
    precio_total = _subtotal_desde_lineas(lineas)

    pedido = models.Pedido.objects.create(
        usuario=usuario,
        tipo_pago=tipo_pago,
        cliente_presencial=cliente_presencial,
        precio_total=precio_total,
        estado_pago=models.Pedido.EstadoPago.PENDIENTE,
    )

    for linea in lineas:
        models.PedidoProducto.objects.create(
            pedido=pedido,
            producto=linea["producto"],
            precio_unitario=linea["precio_unitario"],
            cantidad=linea["cantidad"],
            subtotal=linea["subtotal"],
        )

    return pedido


@transaction.atomic
def crear_pedido_desde_carrito(usuario):
    if _pedido_web_abierto(usuario):
        raise ValidationError(
            "Ya tienes un pedido pendiente de pago. "
            "Completa el pago o espera a que finalice antes de crear otro."
        )

    try:
        carrito = models.CarritoCompra.objects.select_for_update().get(usuario=usuario)
    except models.CarritoCompra.DoesNotExist:
        raise ValidationError("No tienes productos en el carrito.")

    items = list(models.ProductoCarrito.objects.filter(carrito_compra=carrito))
    if not items:
        raise ValidationError("El carrito está vacío.")

    productos_map = _bloquear_productos(item.producto_id for item in items)
    lineas = _construir_lineas(
        ((item.producto_id, item.cantidad) for item in items),
        productos_map,
    )

    return _persistir_pedido(
        usuario=usuario,
        tipo_pago=None,
        cliente_presencial=False,
        lineas=lineas,
    )


@transaction.atomic
def crear_pedido_presencial(usuario, items, tipo_pago):
    if tipo_pago not in TIPOS_PAGO_PRESENCIAL:
        raise ValidationError('El tipo de pago debe ser "efectivo" o "credito".')

    if not items:
        raise ValidationError("Debe incluir al menos un producto.")

    producto_ids = [item["producto_id"] for item in items]
    productos_map = _bloquear_productos(producto_ids)

    faltantes = set(producto_ids) - productos_map.keys()
    if faltantes:
        raise ValidationError(f"Productos no encontrados: {sorted(faltantes)}.")

    lineas = _construir_lineas(
        ((item["producto_id"], item["cantidad"]) for item in items),
        productos_map,
    )

    return _persistir_pedido(
        usuario=usuario,
        tipo_pago=tipo_pago,
        cliente_presencial=True,
        lineas=lineas,
    )


def _validar_pedido_para_credito(pedido):
    if not pedido.cliente_presencial:
        raise ValidationError("Solo pedidos presenciales pueden financiarse a crédito.")
    if pedido.tipo_pago != models.Pedido.TipoPago.CREDITO:
        raise ValidationError('El pedido debe tener tipo_pago="credito".')
    if not pedido.usuario_id:
        raise ValidationError("El pedido a crédito debe tener un usuario asociado.")
    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError("El pedido ya está confirmado.")
    _validar_pedido_editable(pedido)

    from apps.creditos.models import Credito

    if Credito.objects.filter(
        pedido=pedido, fecha_eliminacion__isnull=True
    ).exists():
        raise ValidationError("Este pedido ya tiene un crédito asociado.")


@transaction.atomic
def crear_credito_para_pedido(
    pedido_id,
    cantidad_cuotas,
    interes,
    frecuencia_dias=30,
    observaciones="",
):
    from apps.creditos.services import crear_credito

    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    _validar_pedido_para_credito(pedido)

    try:
        credito = crear_credito(
            pedido=pedido,
            usuario=pedido.usuario,
            cantidad_cuotas=cantidad_cuotas,
            interes=interes,
            valor_total=pedido.precio_total,
            frecuencia_dias=frecuencia_dias,
            observaciones=observaciones,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    _descontar_stock_pedido(pedido)
    pedido.estado_pago = models.Pedido.EstadoPago.APROBADO
    pedido.fecha_pago = timezone.now()
    pedido.save(update_fields=["estado_pago", "fecha_pago"])

    return pedido, credito


@transaction.atomic
def crear_pedido_presencial_con_credito(
    usuario,
    items,
    cantidad_cuotas,
    interes,
    frecuencia_dias=30,
    observaciones="",
):
    if not usuario:
        raise ValidationError("Un pedido a crédito requiere un usuario asociado.")

    pedido = crear_pedido_presencial(
        usuario=usuario,
        items=items,
        tipo_pago=models.Pedido.TipoPago.CREDITO,
    )

    _, credito = crear_credito_para_pedido(
        pedido_id=pedido.id,
        cantidad_cuotas=cantidad_cuotas,
        interes=interes,
        frecuencia_dias=frecuencia_dias,
        observaciones=observaciones,
    )
    pedido.refresh_from_db()
    return pedido, credito


def obtener_datos_pago_wompi(pedido_id, usuario):
    try:
        pedido = models.Pedido.objects.get(pk=pedido_id, usuario=usuario)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.cliente_presencial:
        raise ValidationError("Este pedido no utiliza pago online.")
    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError("Este pedido ya fue pagado.")
    if pedido.estado_pago not in _ESTADOS_PAGO_ABIERTO:
        raise ValidationError(
            f'No se puede iniciar pago con estado "{pedido.estado_pago}".'
        )

    if pedido.estado_pago == models.Pedido.EstadoPago.RECHAZADO:
        pedido.referencia_wompi = None
        pedido.estado_pago = models.Pedido.EstadoPago.PENDIENTE
        pedido.save(update_fields=["referencia_wompi", "estado_pago"])

    return wompi.datos_checkout(pedido)


@transaction.atomic
def confirmar_pago_wompi(
    pedido_id, id_transaccion_wompi, monto_centavos=None, medio_pago=None
):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.cliente_presencial:
        raise ValidationError("Este pedido no se confirma por Wompi.")
    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError("El pedido ya fue confirmado.")

    if pedido.estado_pago not in _ESTADOS_PAGO_ABIERTO:
        raise ValidationError(
            f'No se puede confirmar un pago en estado "{pedido.estado_pago}".'
        )

    if monto_centavos is not None:
        esperado = wompi.precio_total_en_centavos(pedido.precio_total)
        if int(monto_centavos) != esperado:
            raise ValidationError(
                f"Monto de la transacción ({monto_centavos} centavos) no coincide "
                f"con el total del pedido ({esperado} centavos)."
            )

    _descontar_stock_pedido(pedido)

    pedido.tipo_pago = models.Pedido.TipoPago.WOMPI
    pedido.medio_pago = medio_pago or ""
    pedido.estado_pago = models.Pedido.EstadoPago.APROBADO
    pedido.id_transaccion_wompi = id_transaccion_wompi
    pedido.fecha_pago = timezone.now()
    pedido.save()

    if pedido.usuario_id:
        vaciar_carrito(pedido.usuario)

    return pedido


@transaction.atomic
def rechazar_pago_wompi(pedido_id, id_transaccion_wompi):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError("El pedido ya fue confirmado.")
    if pedido.estado_pago == models.Pedido.EstadoPago.RECHAZADO:
        return pedido

    if pedido.estado_pago != models.Pedido.EstadoPago.PENDIENTE:
        raise ValidationError(
            f'No se puede rechazar un pago en estado "{pedido.estado_pago}".'
        )

    pedido.estado_pago = models.Pedido.EstadoPago.RECHAZADO
    pedido.id_transaccion_wompi = id_transaccion_wompi
    pedido.save()
    return pedido


@transaction.atomic
def confirmar_pago_manual(pedido_id):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if not pedido.cliente_presencial:
        raise ValidationError(
            "La confirmación manual solo aplica a pedidos presenciales."
        )
    if pedido.tipo_pago == models.Pedido.TipoPago.CREDITO:
        raise ValidationError(
            "Los pedidos a crédito se confirman registrando el plan de cuotas "
            "(POST .../credito/ o presencial con bloque credito)."
        )
    if pedido.tipo_pago != models.Pedido.TipoPago.EFECTIVO:
        raise ValidationError('La confirmación manual solo aplica a pedidos en "efectivo".')

    _validar_pedido_editable(pedido)

    if pedido.estado_pago != models.Pedido.EstadoPago.PENDIENTE:
        raise ValidationError(
            f'El pedido ya tiene estado de pago "{pedido.estado_pago}".'
        )

    _descontar_stock_pedido(pedido)

    pedido.estado_pago = models.Pedido.EstadoPago.APROBADO
    pedido.fecha_pago = timezone.now()
    pedido.save()
    return pedido


@transaction.atomic
def cancelar_pedido_admin(pedido_id):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    _validar_pedido_editable(pedido)

    if pedido.estado_pago not in _ESTADOS_PAGO_ABIERTO:
        raise ValidationError(
            f'No se puede cancelar un pedido en estado "{pedido.estado_pago}".'
        )

    pedido.estado_pago = models.Pedido.EstadoPago.RECHAZADO
    pedido.save(update_fields=["estado_pago"])
    return pedido
