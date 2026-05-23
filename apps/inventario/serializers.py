from rest_framework import serializers
from decimal import Decimal
from django.core.validators import MinValueValidator
from . import models
from . import validators as my_validators


class IngredienteSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(validators=[my_validators.validate_non_empty_string])
    proveedor = serializers.CharField(validators=[my_validators.validate_non_empty_string])
    stock_actual = serializers.DecimalField(validators=[my_validators.validate_positive_decimal_gt_zero], max_digits=10, decimal_places=2)
    stock_minimo = serializers.DecimalField(validators=[my_validators.validate_positive_decimal_gt_zero], max_digits=10, decimal_places=2)

    class Meta:
        model = models.Ingrediente
        fields = '__all__'


class ProductoSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(validators=[my_validators.validate_non_empty_string])
    precio = serializers.DecimalField(max_digits=10, decimal_places=2, validators=[my_validators.validate_positive_decimal_gt_zero])
    stock_actual = serializers.IntegerField(min_value=0)
    stock_minimo = serializers.IntegerField(min_value=0)

    class Meta:
        model = models.Producto
        fields = '__all__'


class ProductoIngredienteSerializer(serializers.ModelSerializer):
    cantidad_producida = serializers.IntegerField(min_value=1)
    cantidad_ingrediente = serializers.DecimalField(validators=[my_validators.validate_positive_decimal_gt_zero], max_digits=10, decimal_places=2)
    porcentaje_ingrediente = serializers.DecimalField(validators=[my_validators.validate_percentage], max_digits=5, decimal_places=2)

    class Meta:
        model = models.ProductoIngrediente
        fields = '__all__'


class ProduccionSerializer(serializers.ModelSerializer):
    cantidad_producida = serializers.IntegerField(min_value=1)
    fecha = serializers.DateField(read_only=True)

    class Meta:
        model = models.Produccion
        fields = '__all__'


class MovimientoIngredienteSerializer(serializers.ModelSerializer):
    stock_anterior = serializers.IntegerField(read_only=True)
    stock_posterior = serializers.IntegerField(read_only=True)
    cantidad = serializers.IntegerField(min_value=1)
    fecha = serializers.DateField(read_only=True)

    class Meta:
        model = models.MovimientoIngrediente
        fields = '__all__'


class MovimientoProductoSerializer(serializers.ModelSerializer):
    stock_anterior = serializers.IntegerField(read_only=True)
    stock_posterior = serializers.IntegerField(read_only=True)
    cantidad = serializers.IntegerField(min_value=1)
    fecha = serializers.DateField(read_only=True)

    class Meta:
        model = models.MovimientoProducto
        fields = '__all__'

