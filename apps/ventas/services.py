# ventas/services.py

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
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

_ESTADOS_REQUIEREN_PAGO_APROBADO = frozenset(
    {
        models.Pedido.EstadoPedido.PREPARANDO,
        models.Pedido.EstadoPedido.ENVIADO,
        models.Pedido.EstadoPedido.ENTREGADO,
    }
)


def _validar_pago_para_estado_fulfillment(pedido, nuevo_estado):
    if nuevo_estado not in _ESTADOS_REQUIEREN_PAGO_APROBADO:
        return
    if pedido.tipo_pago == models.Pedido.TipoPago.CREDITO:
        return
    if pedido.estado_pago != models.Pedido.EstadoPago.APROBADO:
        raise ValidationError("No se puede avanzar el pedido sin pago aprobado.")


_TRANSICIONES_PEDIDO = {
    models.Pedido.EstadoPedido.PENDIENTE: models.Pedido.EstadoPedido.CONFIRMADO,
    models.Pedido.EstadoPedido.CONFIRMADO: models.Pedido.EstadoPedido.PREPARANDO,
    models.Pedido.EstadoPedido.PREPARANDO: models.Pedido.EstadoPedido.ENVIADO,
    models.Pedido.EstadoPedido.ENVIADO: models.Pedido.EstadoPedido.ENTREGADO,
}


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
    total_productos = Decimal("0.00")

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
        total_productos += subtotal

        lineas.append(
            {
                "producto": producto,
                "cantidad": cantidad,
                "precio_unitario": producto.precio,
                "subtotal": subtotal,
            }
        )

    return lineas, total_productos


def _subtotal_desde_lineas(lineas) -> Decimal:
    return sum((linea["subtotal"] for linea in lineas), Decimal("0.00"))


def _subtotal_pedido(pedido) -> Decimal:
    return sum(
        (linea.subtotal for linea in pedido.pedidoproducto_set.all()),
        Decimal("0.00"),
    )


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


def _persistir_pedido(
    usuario,
    tipo_pago,
    cliente_presencial,
    direccion_envio,
    costo_envio,
    coordenadas_lat,
    coordenadas_lng,
    lineas,
    aprobado_admin=False,
    descontar_stock=False,
):
    total_productos = _subtotal_desde_lineas(lineas)
    precio_total = total_productos + costo_envio

    pedido = models.Pedido.objects.create(
        usuario=usuario,
        tipo_pago=tipo_pago,
        cliente_presencial=cliente_presencial,
        direccion_envio=direccion_envio,
        coordenadas_lat=coordenadas_lat,
        coordenadas_lng=coordenadas_lng,
        estado_pedido=models.Pedido.EstadoPedido.PENDIENTE,
        estado_pago=models.Pedido.EstadoPago.PENDIENTE,
        costo_envio=costo_envio,
        precio_total=precio_total,
        aprobado_admin=aprobado_admin,
    )

    for linea in lineas:
        models.PedidoProducto.objects.create(
            pedido=pedido,
            producto=linea["producto"],
            precio_unitario=linea["precio_unitario"],
            cantidad=linea["cantidad"],
            subtotal=linea["subtotal"],
        )

    if descontar_stock:
        _descontar_stock_pedido(pedido)

    return pedido


def limpiar_carritos_expirados():
    minutos = getattr(settings, "CARRITO_CHECKOUT_EXPIRACION_MINUTOS", 30)
    limite = timezone.now() - timedelta(minutes=minutos)

    carritos_expirados = models.CarritoCompra.objects.filter(
        estado__in=(
            models.CarritoCompra.Estado.CHECKOUT,
            models.CarritoCompra.Estado.ABANDONADO,
        ),
        fecha_actualizacion__lt=limite,
    )

    for carrito in carritos_expirados:
        models.ProductoCarrito.objects.filter(carrito_compra=carrito).delete()
        carrito.estado = models.CarritoCompra.Estado.ACTIVO
        carrito.save(update_fields=["estado"])


def obtener_o_crear_carrito(usuario):
    limpiar_carritos_expirados()

    try:
        carrito = models.CarritoCompra.objects.get(usuario=usuario)
    except models.CarritoCompra.DoesNotExist:
        return models.CarritoCompra.objects.create(
            usuario=usuario,
            estado=models.CarritoCompra.Estado.ACTIVO,
        )

    estados_a_resetear = (
        models.CarritoCompra.Estado.COMPLETADO,
        models.CarritoCompra.Estado.ABANDONADO,
        models.CarritoCompra.Estado.CHECKOUT,
    )
    if carrito.estado in estados_a_resetear:
        models.ProductoCarrito.objects.filter(carrito_compra=carrito).delete()
        carrito.estado = models.CarritoCompra.Estado.ACTIVO
        carrito.save()

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
            carrito_compra__estado=models.CarritoCompra.Estado.ACTIVO,
            producto_id=producto_id,
        )
    except models.ProductoCarrito.DoesNotExist:
        raise ValidationError("El producto no está en el carrito activo.")

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
        carrito_compra__estado=models.CarritoCompra.Estado.ACTIVO,
        producto_id=producto_id,
    ).delete()

    if eliminados == 0:
        raise ValidationError("El producto no estaba en el carrito activo.")


def abandonar_carrito(usuario):
    actualizado = models.CarritoCompra.objects.filter(
        usuario=usuario,
        estado=models.CarritoCompra.Estado.ACTIVO,
    ).update(estado=models.CarritoCompra.Estado.ABANDONADO)

    if actualizado == 0:
        raise ValidationError("No hay un carrito activo para abandonar.")


@transaction.atomic
def crear_pedido_desde_carrito(
    usuario,
    tipo_pago,
    direccion_envio,
    coordenadas_lat=None,
    coordenadas_lng=None,
):
    if tipo_pago in TIPOS_PAGO_PRESENCIAL:
        raise ValidationError(
            'Los métodos "efectivo" y "crédito" son exclusivos de pedidos presenciales.'
        )

    try:
        carrito = models.CarritoCompra.objects.select_for_update().get(
            usuario=usuario,
            estado=models.CarritoCompra.Estado.ACTIVO,
        )
    except models.CarritoCompra.DoesNotExist:
        raise ValidationError("No existe un carrito activo para este usuario.")

    items = list(models.ProductoCarrito.objects.filter(carrito_compra=carrito))
    if not items:
        raise ValidationError("El carrito está vacío.")

    carrito.estado = models.CarritoCompra.Estado.CHECKOUT
    carrito.save()

    productos_map = _bloquear_productos(item.producto_id for item in items)
    lineas, _total_productos = _construir_lineas(
        ((item.producto_id, item.cantidad) for item in items),
        productos_map,
    )

    pedido = _persistir_pedido(
        usuario=usuario,
        tipo_pago=tipo_pago,
        cliente_presencial=False,
        direccion_envio=direccion_envio,
        costo_envio=Decimal("0.00"),
        coordenadas_lat=coordenadas_lat,
        coordenadas_lng=coordenadas_lng,
        lineas=lineas,
        aprobado_admin=False,
        descontar_stock=False,
    )

    carrito.estado = models.CarritoCompra.Estado.COMPLETADO
    carrito.save()

    return pedido


@transaction.atomic
def crear_pedido_presencial(
    usuario,
    items,
    tipo_pago,
    direccion_envio="",
    costo_envio=Decimal("0.00"),
    coordenadas_lat=None,
    coordenadas_lng=None,
):
    if not items:
        raise ValidationError("Debe incluir al menos un producto.")

    producto_ids = [item["producto_id"] for item in items]
    productos_map = _bloquear_productos(producto_ids)

    faltantes = set(producto_ids) - productos_map.keys()
    if faltantes:
        raise ValidationError(f"Productos no encontrados: {sorted(faltantes)}.")

    lineas, _total_productos = _construir_lineas(
        ((item["producto_id"], item["cantidad"]) for item in items),
        productos_map,
    )

    return _persistir_pedido(
        usuario=usuario,
        tipo_pago=tipo_pago,
        cliente_presencial=True,
        direccion_envio=direccion_envio,
        costo_envio=Decimal(str(costo_envio)),
        coordenadas_lat=coordenadas_lat,
        coordenadas_lng=coordenadas_lng,
        lineas=lineas,
        aprobado_admin=True,
        descontar_stock=False,
    )


@transaction.atomic
def aprobar_pedido_online(pedido_id, costo_envio):
    if costo_envio < 0:
        raise ValidationError("El costo de envío no puede ser negativo.")

    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.cliente_presencial:
        raise ValidationError(
            "La aprobación con costo de envío solo aplica a pedidos online."
        )
    if pedido.estado_pedido == models.Pedido.EstadoPedido.CANCELADO:
        raise ValidationError("No se puede aprobar un pedido cancelado.")
    if pedido.aprobado_admin:
        raise ValidationError("El pedido ya fue revisado por un administrador.")

    subtotal = _subtotal_pedido(pedido)
    pedido.costo_envio = Decimal(str(costo_envio))
    pedido.precio_total = subtotal + pedido.costo_envio
    pedido.aprobado_admin = True
    pedido.save()
    return pedido


@transaction.atomic
def cancelar_pedido_admin(pedido_id):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.estado_pedido == models.Pedido.EstadoPedido.CANCELADO:
        raise ValidationError("El pedido ya está cancelado.")
    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError(
            "No se puede cancelar un pedido con pago ya aprobado. "
            "Gestione la devolución de forma manual."
        )

    pedido.estado_pedido = models.Pedido.EstadoPedido.CANCELADO
    if pedido.estado_pago == models.Pedido.EstadoPago.PENDIENTE:
        pedido.estado_pago = models.Pedido.EstadoPago.RECHAZADO
    pedido.save()
    return pedido


def obtener_datos_pago_wompi(pedido_id, usuario):
    try:
        pedido = models.Pedido.objects.get(pk=pedido_id, usuario=usuario)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.cliente_presencial:
        raise ValidationError("Este pedido no utiliza pago online.")
    if not pedido.aprobado_admin:
        raise ValidationError(
            "El pedido aún no ha sido revisado. "
            "Espere a que el administrador defina el costo de envío."
        )
    if pedido.estado_pedido == models.Pedido.EstadoPedido.CANCELADO:
        raise ValidationError("El pedido fue cancelado.")
    if pedido.estado_pago != models.Pedido.EstadoPago.PENDIENTE:
        raise ValidationError(
            f'El pedido ya tiene estado de pago "{pedido.estado_pago}".'
        )

    return wompi.datos_checkout(pedido)


@transaction.atomic
def confirmar_pago_wompi(pedido_id, id_transaccion_wompi, monto_centavos=None):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if not pedido.aprobado_admin:
        raise ValidationError(
            "No se puede confirmar el pago de un pedido no aprobado por el administrador."
        )
    if pedido.estado_pago != models.Pedido.EstadoPago.PENDIENTE:
        raise ValidationError(
            f'El pedido ya tiene estado de pago "{pedido.estado_pago}".'
        )

    if monto_centavos is not None:
        esperado = wompi.precio_total_en_centavos(pedido.precio_total)
        if int(monto_centavos) != esperado:
            raise ValidationError(
                f"Monto de la transacción ({monto_centavos} centavos) no coincide "
                f"con el total del pedido ({esperado} centavos)."
            )

    _descontar_stock_pedido(pedido)

    pedido.estado_pago = models.Pedido.EstadoPago.APROBADO
    pedido.id_transaccion_wompi = id_transaccion_wompi
    pedido.fecha_pago = timezone.now()
    pedido.save()
    return pedido


@transaction.atomic
def rechazar_pago_wompi(pedido_id, id_transaccion_wompi):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.estado_pago != models.Pedido.EstadoPago.PENDIENTE:
        raise ValidationError(
            f'El pedido ya tiene estado de pago "{pedido.estado_pago}".'
        )

    pedido.estado_pago = models.Pedido.EstadoPago.RECHAZADO
    pedido.estado_pedido = models.Pedido.EstadoPedido.CANCELADO
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
    if pedido.estado_pago != models.Pedido.EstadoPago.PENDIENTE:
        raise ValidationError(
            f'El pedido ya tiene estado de pago "{pedido.estado_pago}".'
        )

    if not pedido.aprobado_admin:
        raise ValidationError(
            "Defina el costo de envío antes de confirmar el pago presencial."
        )

    _descontar_stock_pedido(pedido)

    pedido.estado_pago = models.Pedido.EstadoPago.APROBADO
    pedido.fecha_pago = timezone.now()
    pedido.save()
    return pedido


@transaction.atomic
def actualizar_estado_pedido(pedido_id, nuevo_estado):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.estado_pedido == models.Pedido.EstadoPedido.CANCELADO:
        raise ValidationError("No se puede modificar un pedido cancelado.")
    if pedido.estado_pedido == models.Pedido.EstadoPedido.ENTREGADO:
        raise ValidationError("No se puede modificar un pedido ya entregado.")

    estados_validos = {c.value for c in models.Pedido.EstadoPedido}
    if nuevo_estado not in estados_validos:
        raise ValidationError(f'Estado de pedido inválido: "{nuevo_estado}".')

    _validar_pago_para_estado_fulfillment(pedido, nuevo_estado)
    pedido.estado_pedido = nuevo_estado
    pedido.save()
    return pedido


@transaction.atomic
def avanzar_estado_pedido(pedido_id):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError("Pedido no encontrado.")

    if pedido.estado_pedido == models.Pedido.EstadoPedido.CANCELADO:
        raise ValidationError("No se puede avanzar un pedido cancelado.")

    excepcion_credito = pedido.tipo_pago == models.Pedido.TipoPago.CREDITO
    if (
        pedido.estado_pago != models.Pedido.EstadoPago.APROBADO
        and not excepcion_credito
    ):
        raise ValidationError("No se puede avanzar el estado sin pago aprobado.")

    siguiente = _TRANSICIONES_PEDIDO.get(pedido.estado_pedido)
    if siguiente is None:
        raise ValidationError(
            f'El pedido ya está en su estado final: "{pedido.estado_pedido}".'
        )

    _validar_pago_para_estado_fulfillment(pedido, siguiente)
    pedido.estado_pedido = siguiente
    pedido.save()
    return pedido
