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
                f"El producto '{producto.nombre}' (ID: {producto.id}) ya no está disponible. "
                "Ha sido deshabilitado del inventario."
            )
        if producto.stock_actual < cantidad:
            raise ValidationError(
                f"Stock insuficiente para '{producto.nombre}' (ID: {producto.id}). "
                f"Disponible: {producto.stock_actual} unidades, requerido: {cantidad}."
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
        raise ValidationError(
            f"No se puede modificar el pedido #{pedido.id}: ya está confirmado y pagado."
        )


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
        raise ValidationError(
            f"La cantidad de productos debe ser al menos 1. Recibido: {cantidad}."
        )

    carrito = obtener_o_crear_carrito(usuario)

    try:
        producto = inventario_models.Producto.objects.get(
            pk=producto_id, inhabilitado=False
        )
    except inventario_models.Producto.DoesNotExist:
        raise ValidationError(
            f"Producto (ID: {producto_id}) no encontrado o ya no está disponible. "
            "Verifique que el producto existe y no ha sido deshabilitado."
        )

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
            f"Stock insuficiente para '{producto.nombre}'. "
            f"Disponible: {producto.stock_actual} unidades, total solicitado: {nueva_cantidad}."
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
        raise ValidationError(
            f"La cantidad de productos debe ser al menos 1. Recibido: {cantidad}."
        )

    try:
        producto_carrito = models.ProductoCarrito.objects.select_related(
            "producto"
        ).get(
            carrito_compra__usuario=usuario,
            producto_id=producto_id,
        )
    except models.ProductoCarrito.DoesNotExist:
        raise ValidationError(
            f"El producto (ID: {producto_id}) no está en el carrito de compras."
        )

    if producto_carrito.producto.stock_actual < cantidad:
        raise ValidationError(
            f"Stock insuficiente para '{producto_carrito.producto.nombre}'. "
            f"Disponible: {producto_carrito.producto.stock_actual} unidades, solicitado: {cantidad}."
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
        raise ValidationError(
            f"El producto (ID: {producto_id}) no estaba en el carrito de compras."
        )


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
            f"Ya existe un pedido pendiente de pago. Debe completar el pago o "
            "esperar a que finalice ese pedido antes de crear otro."
        )

    try:
        carrito = models.CarritoCompra.objects.select_for_update().get(usuario=usuario)
    except models.CarritoCompra.DoesNotExist:
        raise ValidationError(
            "No tienes productos en el carrito. Anade al menos un producto antes de proceder al pago."
        )

    items = list(models.ProductoCarrito.objects.filter(carrito_compra=carrito))
    if not items:
        raise ValidationError(
            "El carrito esta vacio. Anade productos antes de crear un pedido."
        )

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
        raise ValidationError(
            f"Tipo de pago '{tipo_pago}' no valido. Valores permitidos: efectivo, credito."
        )

    if not items:
        raise ValidationError(
            "Debe incluir al menos un producto en el pedido."
        )

    producto_ids = [item["producto_id"] for item in items]
    productos_map = _bloquear_productos(producto_ids)

    faltantes = set(producto_ids) - productos_map.keys()
    if faltantes:
        raise ValidationError(
            f"Los siguientes productos no se encontraron o no estan disponibles: {sorted(faltantes)}."
        )

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
        raise ValidationError(
            f"No se puede crear credito: el pedido #{pedido.id} es de venta en linea. "
            "Solo se permite credito para pedidos presenciales."
        )
    if pedido.tipo_pago != models.Pedido.TipoPago.CREDITO:
        raise ValidationError(
            f"No se puede crear credito: el pedido #{pedido.id} tiene tipo_pago '{pedido.get_tipo_pago_display()}'. "
            "Debe ser 'Credito'."
        )
    if not pedido.usuario_id:
        raise ValidationError(
            f"No se puede crear credito para el pedido #{pedido.id}: debe tener un usuario/cliente asociado."
        )
    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError(
            f"No se puede crear credito: el pedido #{pedido.id} ya esta confirmado y pagado."
        )
    _validar_pedido_editable(pedido)

    from apps.creditos.models import Credito

    if Credito.objects.filter(
        pedido=pedido, fecha_eliminacion__isnull=True
    ).exists():
        raise ValidationError(
            f"No se puede crear credito: el pedido #{pedido.id} ya tiene un plan de financiacion activo."
        )


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
        raise ValidationError(
            f"Pedido (ID: {pedido_id}) no encontrado. Verifique que el ID sea correcto."
        )

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
        raise ValidationError(
            "No se puede crear pedido a credito sin un cliente/usuario asociado. "
            "Especifique el usuario para proceder."
        )

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
        raise ValidationError(
            f"Pedido (ID: {pedido_id}) no encontrado para el usuario '{usuario.correo}'."
        )

    if pedido.cliente_presencial:
        raise ValidationError(
            f"El pedido #{pedido.id} es presencial y no utiliza pago online (Wompi)."
        )
    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError(
            f"El pedido #{pedido.id} ya fue pagado. No se puede iniciar otro pago."
        )
    if pedido.estado_pago not in _ESTADOS_PAGO_ABIERTO:
        raise ValidationError(
            f"No se puede iniciar pago: el pedido #{pedido.id} tiene estado '{pedido.get_estado_pago_display()}'. "
            f"Solo se puede pagar en estado 'Pendiente' o 'Rechazado'."
        )

    if pedido.estado_pago == models.Pedido.EstadoPago.RECHAZADO:
        pedido.referencia_wompi = None
        pedido.estado_pago = models.Pedido.EstadoPago.PENDIENTE
        pedido.save(update_fields=["referencia_wompi", "estado_pago"])
    elif pedido.referencia_wompi and pedido.estado_pago == models.Pedido.EstadoPago.PENDIENTE:
        pedido.referencia_wompi = None
        pedido.save(update_fields=["referencia_wompi"])

    return wompi.datos_checkout(pedido)


@transaction.atomic
def confirmar_pago_wompi(
    pedido_id, id_transaccion_wompi, monto_centavos=None, medio_pago=None
):
    try:
        pedido = models.Pedido.objects.select_for_update().get(pk=pedido_id)
    except models.Pedido.DoesNotExist:
        raise ValidationError(
            f"Pedido (ID: {pedido_id}) no encontrado. Verifique que el ID sea correcto."
        )

    if pedido.cliente_presencial:
        raise ValidationError(
            f"El pedido #{pedido.id} es presencial y no se puede confirmar por Wompi (pago online)."
        )
    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError(
            f"El pedido #{pedido.id} ya fue confirmado y pagado. No se puede procesarlo nuevamente."
        )

    if pedido.estado_pago not in _ESTADOS_PAGO_ABIERTO:
        raise ValidationError(
            f"No se puede confirmar pago: el pedido #{pedido.id} tiene estado '{pedido.get_estado_pago_display()}'. "
            f"Solo se puede pagar en estado 'Pendiente' o 'Rechazado'."
        )

    if monto_centavos is not None:
        esperado = wompi.precio_total_en_centavos(pedido.precio_total)
        if int(monto_centavos) != esperado:
            raise ValidationError(
                f"Monto de la transaccion (${monto_centavos / 100:.2f}) no coincide con el total "
                f"del pedido #{pedido.id} (${esperado / 100:.2f}). Transaccion rechazada."
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
        raise ValidationError(
            f"Pedido (ID: {pedido_id}) no encontrado. Verifique que el ID sea correcto."
        )

    if pedido.estado_pago == models.Pedido.EstadoPago.APROBADO:
        raise ValidationError(
            f"No se puede rechazar: el pedido #{pedido.id} ya fue confirmado y pagado."
        )
    if pedido.estado_pago == models.Pedido.EstadoPago.RECHAZADO:
        return pedido

    if pedido.estado_pago != models.Pedido.EstadoPago.PENDIENTE:
        raise ValidationError(
            f"No se puede rechazar pago: el pedido #{pedido.id} tiene estado '{pedido.get_estado_pago_display()}'. "
            f"Solo se puede rechazar en estado 'Pendiente'."
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
        raise ValidationError(
            f"Pedido (ID: {pedido_id}) no encontrado. Verifique que el ID sea correcto."
        )

    if not pedido.cliente_presencial:
        raise ValidationError(
            f"No se puede confirmar pago manual: el pedido #{pedido.id} es de venta en linea. "
            "Solo se permite confirmacion manual para pedidos presenciales."
        )
    if pedido.tipo_pago == models.Pedido.TipoPago.CREDITO:
        raise ValidationError(
            f"No se puede confirmar pago manual: el pedido #{pedido.id} es a credito. "
            "Los pagos de credito se registran mediante el plan de cuotas."
        )
    if pedido.tipo_pago != models.Pedido.TipoPago.EFECTIVO:
        raise ValidationError(
            f"No se puede confirmar pago manual: el pedido #{pedido.id} tiene tipo de pago '{pedido.get_tipo_pago_display()}'. "
            "Solo se permite para tipo 'Contado'."
        )

    _validar_pedido_editable(pedido)

    if pedido.estado_pago != models.Pedido.EstadoPago.PENDIENTE:
        raise ValidationError(
            f"No se puede confirmar pago: el pedido #{pedido.id} ya tiene estado '{pedido.get_estado_pago_display()}'. "
            "Solo se pueden confirmar pedidos en estado 'Pendiente'."
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
        raise ValidationError(
            f"Pedido (ID: {pedido_id}) no encontrado. Verifique que el ID sea correcto."
        )

    _validar_pedido_editable(pedido)

    if pedido.estado_pago not in _ESTADOS_PAGO_ABIERTO:
        raise ValidationError(
            f"No se puede cancelar: el pedido #{pedido.id} tiene estado '{pedido.get_estado_pago_display()}'. "
            f"Solo se pueden cancelar pedidos en estado 'Pendiente' o 'Rechazado'."
        )

    pedido.estado_pago = models.Pedido.EstadoPago.RECHAZADO
    pedido.save(update_fields=["estado_pago"])
    return pedido
