from django.utils import timezone
from datetime import timedelta
from .models import Notificacion


def create_alert(tipo, mensaje, usuario=None, **kwargs):
    """
    Crea una nueva alerta o actualiza una existente para volver a notificar.
    Las fk se pasan por kwargs, por ejemplo: producto=instancia_producto
    """
    # Buscamos si ya existe una alerta (leída o no leída) para el mismo origen
    notificacion = Notificacion.objects.filter(
        tipo=tipo,
        usuario=usuario,
        **kwargs
    ).first()

    if notificacion:
        # Si ya existe, la marcamos como NO leída y actualizamos la fecha y mensaje
        notificacion.leida = False
        notificacion.fecha_generada = timezone.now()
        notificacion.mensaje = mensaje
        notificacion.save(update_fields=['leida', 'fecha_generada', 'mensaje'])
        return notificacion
    else:
        # Si no existe, la creamos
        return Notificacion.objects.create(
            tipo=tipo,
            mensaje=mensaje,
            usuario=usuario,
            **kwargs
        )


def resolve_alert(tipo, usuario=None, **kwargs):
    """
    Resuelve (marca como leída) una alerta si existe y no está leída.
    """
    notificacion = Notificacion.objects.filter(
        tipo=tipo,
        usuario=usuario,
        leida=False,
        **kwargs
    ).first()

    if notificacion:
        notificacion.resolve()
        return notificacion
    return None


def check_stock_alert(
    instance,
    tipo_notificacion,
    nombre_campo_stock="stock_actual",
    nombre_campo_minimo="stock_minimo",
    nombre_instancia="item",
    **kwargs
):
    """
    Método genérico para verificar y generar/resolver alertas de stock bajo.
    
    Args:
        instance: La instancia del objeto (Producto, Ingrediente, etc.)
        tipo_notificacion: El tipo de notificación (de Notificacion.TipoNotificacion)
        nombre_campo_stock: Nombre del campo de stock_actual (default: 'stock_actual')
        nombre_campo_minimo: Nombre del campo de stock_minimo (default: 'stock_minimo')
        nombre_instancia: Nombre legible del objeto para el mensaje (default: 'item')
        **kwargs: Parámetros adicionales para create_alert/resolve_alert (producto=instance, etc.)
    
    Ejemplo de uso:
        check_stock_alert(
            instance=producto,
            tipo_notificacion=Notificacion.TipoNotificacion.STOCK_PRODUCTO,
            nombre_instancia="producto",
            producto=producto
        )
    """
    stock_actual = getattr(instance, nombre_campo_stock)
    stock_minimo = getattr(instance, nombre_campo_minimo)
    
    if stock_actual <= stock_minimo:
        mensaje = f"El {nombre_instancia} '{instance.nombre}' tiene stock bajo ({stock_actual}). Mínimo: {stock_minimo}."
        create_alert(
            tipo=tipo_notificacion,
            mensaje=mensaje,
            **kwargs
        )
    else:
        resolve_alert(
            tipo=tipo_notificacion,
            **kwargs
        )


def check_expiry_alert(
    instance,
    tipo_notificacion,
    nombre_campo_fecha="fecha_vencimiento",
    dias_alerta=7,
    nombre_instancia="item",
    **kwargs
):
    """
    Método genérico para verificar y generar/resolver alertas de vencimiento próximo.
    
    Args:
        instance: La instancia del objeto (Produccion, etc.)
        tipo_notificacion: El tipo de notificación (de Notificacion.TipoNotificacion)
        nombre_campo_fecha: Nombre del campo de fecha de vencimiento (default: 'fecha_vencimiento')
        dias_alerta: Cantidad de días antes del vencimiento para generar alerta (default: 7)
        nombre_instancia: Nombre legible del objeto para el mensaje
        **kwargs: Parámetros adicionales para create_alert/resolve_alert (producto=instance, etc.)
    
    Ejemplo de uso:
        check_expiry_alert(
            instance=produccion,
            tipo_notificacion=Notificacion.TipoNotificacion.VENCIMIENTO_PRODUCTO,
            nombre_instancia="producto",
            dias_alerta=7,
            producto=produccion.id_producto
        )
    """
    fecha_vencimiento = getattr(instance, nombre_campo_fecha)
    
    if fecha_vencimiento is None:
        return
    
    ahora = timezone.now()
    dias_restantes = (fecha_vencimiento - ahora).days
    
    # Generar alerta si está entre 0 y dias_alerta días para vencer
    if 0 <= dias_restantes <= dias_alerta:
        mensaje = f"El {nombre_instancia} vence en {dias_restantes} días ({fecha_vencimiento.strftime('%d/%m/%Y')})."
        create_alert(
            tipo=tipo_notificacion,
            mensaje=mensaje,
            **kwargs
        )
    # Resolver alerta si ya pasó el vencimiento o si está muy lejos
    elif dias_restantes > dias_alerta or dias_restantes < 0:
        resolve_alert(
            tipo=tipo_notificacion,
            **kwargs
        )
