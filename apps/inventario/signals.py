from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.inventario.models import Producto
from apps.notificaciones.services import create_alert, resolve_alert
from apps.notificaciones.models import Notificacion


@receiver(post_save, sender=Producto)
def check_stock_producto(sender, instance, **kwargs):
    """
    Verifica si el stock del producto cayó por debajo o igual al mínimo.
    Si es así, genera o actualiza la notificación. 
    Si está por encima, la resuelve (marca como leída).
    """
    if instance.stock_actual <= instance.stock_minimo:
        create_alert(
            tipo=Notificacion.TipoNotificacion.STOCK_PRODUCTO,
            mensaje=f"El producto '{instance.nombre}' tiene stock bajo ({instance.stock_actual}). Mínimo: {instance.stock_minimo}.",
            producto=instance
        )
    else:
        resolve_alert(
            tipo=Notificacion.TipoNotificacion.STOCK_PRODUCTO,
            producto=instance
        )
