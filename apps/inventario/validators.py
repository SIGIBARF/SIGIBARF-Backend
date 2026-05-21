from decimal import Decimal
from django.core.exceptions import ValidationError


def validate_non_empty_string(value):
    if not isinstance(value, str) or value.strip() == '':
        raise ValidationError('Este campo no puede ser vacío.')


def validate_positive_decimal_gt_zero(value):
    try:
        v = Decimal(value)
    except Exception:
        raise ValidationError('Valor numérico inválido.')
    if v <= 0:
        raise ValidationError('El valor debe ser mayor que 0.')


def validate_non_negative_int(value):
    if value is None:
        return
    try:
        v = int(value)
    except Exception:
        raise ValidationError('Valor entero inválido.')
    if v < 0:
        raise ValidationError('El valor no puede ser negativo.')


def validate_percentage(value):
    try:
        v = Decimal(value)
    except Exception:
        raise ValidationError('Porcentaje inválido.')
    if v <= 0 or v > 100:
        raise ValidationError('El porcentaje debe ser > 0 y <= 100.')
