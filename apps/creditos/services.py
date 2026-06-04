# services.py
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from .models import Credito, CuotaCredito


@transaction.atomic
def crear_credito(
    pedido,
    usuario,
    cantidad_cuotas: int,
    interes: Decimal,
    valor_total: Decimal,
    frecuencia_dias: int = 30,
    observaciones: str = "",
    fecha_inicio=None,
) -> Credito:
    if cantidad_cuotas < 1:
        raise ValueError("La cantidad de cuotas debe ser mayor a 0.")

    interes_d = Decimal(str(interes))
    valor_total_d = Decimal(str(valor_total))

    if interes_d < 0:
        raise ValueError("El interés no puede ser negativo.")
    if valor_total_d <= 0:
        raise ValueError("El valor total debe ser mayor a 0.")

    if fecha_inicio is None:
        fecha_inicio = timezone.now()

    valor_cuota_base = (valor_total_d / cantidad_cuotas).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    fecha_fin = _sumar_periodos(fecha_inicio, frecuencia_dias, cantidad_cuotas)

    credito = Credito.objects.create(
        pedido=pedido,
        usuario=usuario,
        cantidad_cuotas=cantidad_cuotas,
        valor_total=valor_total_d,
        interes=interes_d,
        valor_cuota=valor_cuota_base,
        frecuencia_dias=frecuencia_dias,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        observaciones=observaciones,
    )

    cuotas = []
    for i in range(1, cantidad_cuotas + 1):
        fv = _sumar_periodos(fecha_inicio, frecuencia_dias, i)
        cuotas.append(
            CuotaCredito(
                credito=credito,
                numero_cuota=i,
                fecha_vencimiento=fv,
                valor_cuota_original=valor_cuota_base,
                incremento_anterior=Decimal("0"),
                valor_cuota_final=valor_cuota_base,
                fecha_ultimo_interes=fv,
            )
        )
    CuotaCredito.objects.bulk_create(cuotas)

    return credito


@transaction.atomic
def registrar_mayor_monto(credito: Credito, monto_entregado) -> dict:
    monto = Decimal(str(monto_entregado))
    if monto <= 0:
        raise ValueError(f"El monto entregado debe ser mayor a $0. Recibido: ${monto}.")

    if credito.estado == Credito.EstadoCredito.PAGADO:
        raise ValueError(
            f"No se puede registrar pago: el crédito #{credito.id} ya está "
            f"completamente pagado (estado: {credito.get_estado_display()})."
        )

    ahora = timezone.now()

    cuotas_abiertas = list(
        credito.cuotas.filter(
            estado__in=[
                CuotaCredito.EstadoCuota.PENDIENTE,
                CuotaCredito.EstadoCuota.PARCIAL,
                CuotaCredito.EstadoCuota.VENCIDA,
            ]
        ).order_by("numero_cuota")
    )

    if not cuotas_abiertas:
        raise ValueError(
            f"No se puede registrar pago: no hay cuotas pendientes en el crédito #{credito.id}. "
            f"Estado actual: {credito.get_estado_display()}."
        )

    afectadas = []
    cuotas_recien_pagadas = []

    for cuota in cuotas_abiertas:
        if monto <= 0:
            break

        aplicar_intereses_vencidos(cuota, ahora, credito.frecuencia_dias)

        saldo_real = cuota.valor_cuota_final - cuota.valor_pagado

        if monto >= saldo_real:
            monto -= saldo_real
            cuota.valor_pagado = cuota.valor_cuota_final
            cuota.estado = CuotaCredito.EstadoCuota.PAGADA
            cuota.fecha_pago = ahora
            cuota.save()
            afectadas.append(
                {
                    "cuota": cuota.numero_cuota,
                    "estado": CuotaCredito.EstadoCuota.PAGADA,
                    "valor_pagado": float(cuota.valor_pagado),
                }
            )
            cuotas_recien_pagadas.append(cuota)

        else:
            cuota.valor_pagado += monto
            cuota.estado = CuotaCredito.EstadoCuota.PARCIAL
            cuota.save()
            afectadas.append(
                {
                    "cuota": cuota.numero_cuota,
                    "estado": CuotaCredito.EstadoCuota.PARCIAL,
                    "valor_pagado": float(cuota.valor_pagado),
                    "saldo_restante": float(
                        cuota.valor_cuota_final - cuota.valor_pagado
                    ),
                }
            )
            monto = Decimal("0")
            break

    if monto > 0:
        raise ValueError(
            f"El monto ingresado (${monto_entregado}) supera el saldo "
            f"pendiente del crédito #{credito.id} en ${monto:.2f}. "
            "Ingrese un monto igual o menor al saldo total."
        )

    cuotas_pagadas_en_recalculo = _recalcular_incrementos(credito)
    todas_pagadas = list(cuotas_recien_pagadas)
    for cuota in cuotas_pagadas_en_recalculo:
        if cuota not in todas_pagadas:
            todas_pagadas.append(cuota)

    if todas_pagadas:
        from .notificaciones import _resolver_alertas_cuota

        for cuota_pagada in todas_pagadas:
            _resolver_alertas_cuota(cuota_pagada)

    for cuota in cuotas_pagadas_en_recalculo:
        ya_incluida = any(
            a["cuota"] == cuota.numero_cuota
            and a["estado"] == CuotaCredito.EstadoCuota.PAGADA
            for a in afectadas
        )
        if not ya_incluida:
            afectadas.append(
                {
                    "cuota": cuota.numero_cuota,
                    "estado": CuotaCredito.EstadoCuota.PAGADA,
                    "valor_pagado": float(cuota.valor_pagado),
                }
            )

    _actualizar_estado_credito(credito, ahora)

    return {"afectadas": afectadas, "sobrante": float(monto)}


def _recalcular_incrementos(credito: Credito) -> list:
    cuotas = list(credito.cuotas.all().order_by("numero_cuota"))
    if not cuotas:
        return

    ahora = timezone.now()

    interes_por_cuota = []
    for c in cuotas:
        interes_acumulado = (
            c.valor_cuota_final - c.valor_cuota_original - c.incremento_anterior
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        interes_por_cuota.append(interes_acumulado)

        c.incremento_anterior = Decimal("0")
        c.valor_cuota_final = (c.valor_cuota_original + interes_acumulado).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    deficit_acumulado = Decimal("0")
    cuotas_a_guardar = []

    for idx, cuota in enumerate(cuotas):
        if cuota.estado == CuotaCredito.EstadoCuota.PAGADA:
            deficit_acumulado = Decimal("0")
            continue

        cuota.incremento_anterior = deficit_acumulado
        cuota.valor_cuota_final = (
            cuota.valor_cuota_original + deficit_acumulado + interes_por_cuota[idx]
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if cuota.estado == CuotaCredito.EstadoCuota.PARCIAL:
            deficit = (cuota.valor_cuota_final - cuota.valor_pagado).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            deficit_acumulado = deficit
        else:
            deficit_acumulado = Decimal("0")

        cuotas_a_guardar.append(cuota)

    if cuotas_a_guardar:
        CuotaCredito.objects.bulk_update(
            cuotas_a_guardar,
            ["incremento_anterior", "valor_cuota_final"],
        )

    cuotas_a_pagar = []
    cuotas_pagadas = []
    for cuota in cuotas:
        if cuota.estado == CuotaCredito.EstadoCuota.PAGADA:
            continue
        if cuota.valor_pagado >= cuota.valor_cuota_final:
            cuota.valor_pagado = cuota.valor_cuota_final
            cuota.estado = CuotaCredito.EstadoCuota.PAGADA
            if cuota.fecha_pago is None:
                cuota.fecha_pago = ahora
            cuotas_a_pagar.append(cuota)
            cuotas_pagadas.append(cuota)
    if cuotas_a_pagar:
        CuotaCredito.objects.bulk_update(
            cuotas_a_pagar,
            ["valor_pagado", "estado", "fecha_pago"],
        )

    return cuotas_pagadas


def _sumar_periodos(fecha_inicio, frecuencia_dias: int, n: int):
    return fecha_inicio + timedelta(days=frecuencia_dias * n)


def aplicar_intereses_vencidos(
    cuota: CuotaCredito, ahora, frecuencia_dias: int
) -> bool:
    tasa = cuota.credito.interes
    if tasa <= 0:
        return False

    if cuota.fecha_vencimiento > ahora:
        return False

    if cuota.fecha_ultimo_interes is None:
        cuota.fecha_ultimo_interes = cuota.fecha_vencimiento

    delta_dias = (ahora - cuota.fecha_ultimo_interes).days
    periodos_nuevos = delta_dias // frecuencia_dias

    if periodos_nuevos <= 0:
        return False

    saldo = (cuota.valor_cuota_final - cuota.valor_pagado).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if saldo <= 0:
        return False

    tasa_d = Decimal(str(tasa))
    factor = (1 + tasa_d) ** periodos_nuevos - 1
    interes_acumulado = (saldo * factor).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    cuota.valor_cuota_final = (cuota.valor_cuota_final + interes_acumulado).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    cuota.fecha_ultimo_interes = cuota.fecha_ultimo_interes + timedelta(
        days=frecuencia_dias * periodos_nuevos
    )
    cuota.save(update_fields=["valor_cuota_final", "fecha_ultimo_interes"])
    return True


def _actualizar_estado_credito(credito: Credito, ahora=None) -> None:
    if ahora is None:
        ahora = timezone.now()

    cuotas = credito.cuotas.all()

    cuotas.filter(
        estado=CuotaCredito.EstadoCuota.PENDIENTE,
        fecha_vencimiento__lt=ahora,
    ).update(estado=CuotaCredito.EstadoCuota.VENCIDA)

    estados = set(cuotas.values_list("estado", flat=True))

    if estados == {CuotaCredito.EstadoCuota.PAGADA}:
        credito.estado = Credito.EstadoCredito.PAGADO
    elif CuotaCredito.EstadoCuota.VENCIDA in estados:
        credito.estado = Credito.EstadoCredito.VENCIDO
    else:
        credito.estado = Credito.EstadoCredito.ACTIVO

    credito.save(update_fields=["estado"])
