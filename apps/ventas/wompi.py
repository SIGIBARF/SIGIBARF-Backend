import hashlib
import hmac
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

ESTADO_APROBADO = "APPROVED"
ESTADOS_RECHAZADO = frozenset({"DECLINED", "VOIDED", "ERROR"})

_PREFIJO_REFERENCIA = "PEDIDO"


def precio_total_en_centavos(precio_total) -> int:
    centavos = (Decimal(precio_total) * 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(centavos)


def generar_referencia(pedido) -> str:
    if pedido.referencia_wompi:
        return pedido.referencia_wompi

    referencia = f"{_PREFIJO_REFERENCIA}-{pedido.id}-{uuid.uuid4().hex}"
    pedido.referencia_wompi = referencia
    pedido.save(update_fields=["referencia_wompi"])
    return referencia


def pedido_id_desde_referencia(referencia: str) -> int | None:
    if not referencia or not referencia.startswith(f"{_PREFIJO_REFERENCIA}-"):
        return None

    resto = referencia[len(_PREFIJO_REFERENCIA) + 1 :]
    pedido_id_str, _, _token = resto.partition("-")
    if not pedido_id_str:
        return None

    try:
        return int(pedido_id_str)
    except ValueError:
        return None


def referencia_pertenece_a_pedido(pedido, referencia: str) -> bool:
    if not pedido.referencia_wompi:
        return True
    return pedido.referencia_wompi == referencia


def generar_firma_integridad(
    referencia: str, monto_centavos: int, moneda: str = "COP"
) -> str:
    cadena = f"{referencia}{monto_centavos}{moneda}{settings.WOMPI_INTEGRITY_KEY}"
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


def verificar_firma_webhook(payload: dict) -> bool:
    try:
        timestamp = payload["timestamp"]
        signature = payload["signature"]
        checksum_recibido = signature["checksum"]
        propiedades = signature["properties"]
        data = payload["data"]

        valores = []
        for ruta in propiedades:
            nodo = data
            for parte in ruta.split("."):
                nodo = nodo[parte]
            valores.append(str(nodo))

        cadena = "".join(valores) + str(timestamp) + settings.WOMPI_EVENTS_SECRET
        checksum_calculado = hashlib.sha256(cadena.encode("utf-8")).hexdigest()

        return hmac.compare_digest(checksum_calculado, checksum_recibido)

    except (KeyError, TypeError, AttributeError):
        return False


def datos_checkout(pedido) -> dict:
    monto_centavos = precio_total_en_centavos(pedido.precio_total)
    referencia = generar_referencia(pedido)

    return {
        "public_key": settings.WOMPI_PUBLIC_KEY,
        "currency": "COP",
        "amount_in_cents": monto_centavos,
        "reference": referencia,
        "integrity": generar_firma_integridad(referencia, monto_centavos),
    }
