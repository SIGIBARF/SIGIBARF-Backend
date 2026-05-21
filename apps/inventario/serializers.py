from rest_framework import serializers
from decimal import Decimal
from django.core.validators import MinValueValidator
import models
import validators as my_validators


class IngredienteSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(validators=[my_validators.validate_non_empty_string])
    proveedor = serializers.CharField(validators=[my_validators.validate_non_empty_string])
    stock_actual = serializers.IntegerField(min_value=0)
    stock_minimo = serializers.IntegerField(min_value=0)

    class Meta:
        model = models.Ingrediente
        fields = '__all__'


class ProductoSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(validators=[my_validators.validate_non_empty_string])
    precio = serializers.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    stock_actual = serializers.IntegerField(min_value=0)
    stock_minimo = serializers.IntegerField(min_value=0)

    class Meta:
        model = models.Producto
        fields = '__all__'


class ProductoIngredienteSerializer(serializers.ModelSerializer):
    porcentaje_ingrediente = serializers.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        model = models.ProductoIngrediente
        fields = '__all__'

    def validate_porcentaje_ingrediente(self, value):
        my_validators.validate_percentage(value)
        return value


class MovimientoIngredienteSerializer(serializers.ModelSerializer):
    stock_anterior = serializers.IntegerField(read_only=True)
    stock_posterior = serializers.IntegerField(read_only=True)
    cantidad = serializers.IntegerField(min_value=1)

    class Meta:
        model = models.MovimientoIngrediente
        fields = '__all__'


class MovimientoProductoSerializer(serializers.ModelSerializer):
    stock_anterior = serializers.IntegerField(read_only=True)
    stock_posterior = serializers.IntegerField(read_only=True)
    cantidad = serializers.IntegerField(min_value=1)

    class Meta:
        model = models.MovimientoProducto
        fields = '__all__'


class ProduccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Produccion
        fields = '__all__'

    def validate_cantidad_producida(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad_producida debe ser mayor que 0.')
        return value
