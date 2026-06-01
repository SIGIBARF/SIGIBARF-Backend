from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.inventario.models import Producto, Ingrediente, Produccion
from apps.notificaciones.services import check_stock_alert, check_expiry_alert
from apps.notificaciones.models import Notificacion


@receiver(post_save, sender=Producto)
def check_stock_producto(sender, instance, **kwargs):
    """
    Verifica si el stock del producto cayó por debajo o igual al mínimo.
    Si es así, genera o actualiza la notificación. 
    Si está por encima, la resuelve (marca como leída).
    """
    check_stock_alert(
        instance=instance,
        tipo_notificacion=Notificacion.TipoNotificacion.STOCK_PRODUCTO,
        nombre_instancia="producto",
        producto=instance
    )


@receiver(post_save, sender=Ingrediente)
def check_stock_ingrediente(sender, instance, **kwargs):
    """
    Verifica si el stock del ingrediente cayó por debajo o igual al mínimo.
    Si es así, genera o actualiza la notificación. 
    Si está por encima, la resuelve (marca como leída).
    """
    check_stock_alert(
        instance=instance,
        tipo_notificacion=Notificacion.TipoNotificacion.STOCK_INGREDIENTE,
        nombre_instancia="ingrediente",
        ingrediente=instance
    )


@receiver(post_save, sender=Produccion)
def check_expiry_producto(sender, instance, **kwargs):
    """
    Verifica si el producto de una producción está próximo a vencer (dentro de 7 días).
    Si es así, genera o actualiza la notificación.
    Si está lejos o ya pasó, la resuelve (marca como leída).
    """
    check_expiry_alert(
        instance=instance,
        tipo_notificacion=Notificacion.TipoNotificacion.VENCIMIENTO_PRODUCTO,
        nombre_instancia="producto",
        dias_alerta=7,  # Alerta 7 días antes del vencimiento
        producto=instance.id_producto
    )
