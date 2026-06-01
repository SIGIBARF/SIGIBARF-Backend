from django.utils import timezone
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
