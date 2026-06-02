from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.inventario.models import Producto

from .models import CarritoCompra, Pedido, PedidoProducto, ProductoCarrito

User = get_user_model()


class ProductoCarritoSerializer(serializers.ModelSerializer):
    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.filter(inhabilitado=False),
        source="producto",
        write_only=True,
    )
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    producto_precio = serializers.DecimalField(
        source="producto.precio", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProductoCarrito
        fields = [
            "id",
            "producto_id",
            "producto_nombre",
            "producto_precio",
            "cantidad",
            "fecha_agregado",
            "carrito_compra",
        ]
        read_only_fields = ["fecha_agregado", "carrito_compra"]

    def validate_cantidad(self, value):
        if value < 1:
            raise serializers.ValidationError("La cantidad mínima es 1.")
        return value

    def validate(self, data):
        producto = data.get("producto")
        cantidad = data.get("cantidad")
        if producto and cantidad and producto.stock_actual < cantidad:
            raise serializers.ValidationError(
                f"Stock insuficiente para '{producto.nombre}'. "
                f"Disponible: {producto.stock_actual}."
            )
        return data


class CarritoCompraSerializer(serializers.ModelSerializer):
    productos = ProductoCarritoSerializer(
        many=True, read_only=True, source="productocarrito_set"
    )
    subtotal_carrito = serializers.SerializerMethodField()

    class Meta:
        model = CarritoCompra
        fields = [
            "id",
            "usuario",
            "fecha_creacion",
            "fecha_actualizacion",
            "productos",
            "subtotal_carrito",
        ]
        read_only_fields = [
            "usuario",
            "fecha_creacion",
            "fecha_actualizacion",
            "subtotal_carrito",
        ]

    def get_subtotal_carrito(self, obj):
        total = Decimal("0.00")
        for item in obj.productocarrito_set.select_related("producto").all():
            total += item.cantidad * item.producto.precio
        return total


class PedidoProductoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = PedidoProducto
        fields = [
            "id",
            "producto",
            "producto_nombre",
            "precio_unitario",
            "cantidad",
            "subtotal",
        ]


class PedidoSerializer(serializers.ModelSerializer):
    productos = PedidoProductoSerializer(
        many=True, source="pedidoproducto_set", read_only=True
    )
    numero_pedido = serializers.IntegerField(source="id", read_only=True)
    listo_para_pago = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id",
            "numero_pedido",
            "tipo_pago",
            "medio_pago",
            "cliente_presencial",
            "precio_total",
            "estado_pago",
            "listo_para_pago",
            "fecha_creacion",
            "fecha_pago",
            "id_transaccion_wompi",
            "productos",
        ]

    def get_listo_para_pago(self, obj):
        return (
            not obj.cliente_presencial
            and obj.estado_pago in (Pedido.EstadoPago.PENDIENTE, Pedido.EstadoPago.RECHAZADO)
        )


class PedidoAdminReadSerializer(PedidoSerializer):
    usuario_id = serializers.IntegerField(
        source="usuario.id", read_only=True, allow_null=True
    )
    usuario_email = serializers.EmailField(
        source="usuario.correo", read_only=True, allow_null=True
    )

    class Meta(PedidoSerializer.Meta):
        fields = PedidoSerializer.Meta.fields + ["usuario_id", "usuario_email"]


class PedidoAdminItemSerializer(serializers.Serializer):
    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.filter(inhabilitado=False),
        source="producto",
    )
    cantidad = serializers.IntegerField(min_value=1)


class PedidoAdminSerializer(serializers.Serializer):
    usuario = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    items = PedidoAdminItemSerializer(many=True)
    tipo_pago = serializers.ChoiceField(
        choices=[
            (Pedido.TipoPago.EFECTIVO, Pedido.TipoPago.EFECTIVO.label),
            (Pedido.TipoPago.CREDITO, Pedido.TipoPago.CREDITO.label),
        ]
    )

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Debe incluir al menos un producto.")

        product_ids = [item["producto"].id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("La lista contiene productos duplicados.")

        errores = []
        for item in value:
            producto = item["producto"]
            if producto.stock_actual < item["cantidad"]:
                errores.append(
                    f"'{producto.nombre}': disponible {producto.stock_actual}, "
                    f"solicitado {item['cantidad']}."
                )
        if errores:
            raise serializers.ValidationError(errores)

        return value
