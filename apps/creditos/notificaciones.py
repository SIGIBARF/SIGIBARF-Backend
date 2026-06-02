# notificaciones.py
from django.utils import timezone

from notificaciones.models import Notificacion
from notificaciones.services import create_alert, resolve_alert

from .models import CuotaCredito


def check_cuota_notifications(cuota: CuotaCredito) -> None:
    if not cuota.notificaciones_activas:
        return

    if cuota.estado == CuotaCredito.EstadoCuota.PAGADA:
        _resolver_alertas_cuota(cuota)
        return

    ahora = timezone.now()
    dias_restantes = (cuota.fecha_vencimiento - ahora).days

    if dias_restantes < 0:
        if _ya_notificado_hoy(
            Notificacion.TipoNotificacion.DEUDA_VENCIDA, cuota_credito=cuota
        ):
            return
        mensaje = (
            f"La cuota #{cuota.numero_cuota} del crédito #{cuota.credito_id} "
            f"está en mora. Venció el "
            f"{cuota.fecha_vencimiento.strftime('%d/%m/%Y')}. "
            f"Saldo pendiente: ${cuota.saldo_pendiente:,.2f}."
        )
        create_alert(
            tipo=Notificacion.TipoNotificacion.DEUDA_VENCIDA,
            mensaje=mensaje,
            cuota_credito=cuota,
        )

    elif 0 <= dias_restantes <= 3:
        if _ya_notificado_hoy(
            Notificacion.TipoNotificacion.DEUDA_PROXIMA, cuota_credito=cuota
        ):
            return
        mensaje = (
            f"La cuota #{cuota.numero_cuota} del crédito #{cuota.credito_id} "
            f"vence en {dias_restantes} día(s) "
            f"({cuota.fecha_vencimiento.strftime('%d/%m/%Y')}). "
            f"Valor a pagar: ${cuota.valor_cuota_final:,.2f}."
        )
        create_alert(
            tipo=Notificacion.TipoNotificacion.DEUDA_PROXIMA,
            mensaje=mensaje,
            cuota_credito=cuota,
        )

    else:
        resolve_alert(
            tipo=Notificacion.TipoNotificacion.DEUDA_PROXIMA,
            cuota_credito=cuota,
        )


def check_credito_notifications(credito) -> None:
    cuotas_abiertas = credito.cuotas.exclude(estado=CuotaCredito.EstadoCuota.PAGADA)
    for cuota in cuotas_abiertas:
        check_cuota_notifications(cuota)


def _ya_notificado_hoy(tipo: str, **kwargs) -> bool:
    hoy = timezone.now().date()
    return Notificacion.objects.filter(
        tipo=tipo,
        fecha_generada__date=hoy,
        **kwargs,
    ).exists()


def _resolver_alertas_cuota(cuota: CuotaCredito) -> None:
    resolve_alert(
        tipo=Notificacion.TipoNotificacion.DEUDA_PROXIMA,
        cuota_credito=cuota,
    )
    resolve_alert(
        tipo=Notificacion.TipoNotificacion.DEUDA_VENCIDA,
        cuota_credito=cuota,
    )
