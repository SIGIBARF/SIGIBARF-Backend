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
    )
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    producto_precio = serializers.DecimalField(
        source="producto.precio", max_digits=10, decimal_places=2, read_only=True
    )
    producto_imagen = serializers.CharField(
        source="producto.imagen", read_only=True, allow_null=True
    )

    class Meta:
        model = ProductoCarrito
        fields = [
            "id",
            "producto_id",
            "producto_nombre",
            "producto_precio",
            "producto_imagen",
            "cantidad",
            "fecha_agregado",
            "carrito_compra",
        ]
        read_only_fields = ["fecha_agregado", "carrito_compra", "producto_id"]

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
    usuario = serializers.SerializerMethodField()

    class Meta(PedidoSerializer.Meta):
        fields = PedidoSerializer.Meta.fields + ["usuario_id", "usuario_email", "usuario"]

    def get_usuario(self, obj):
        if obj.usuario:
            return f"{obj.usuario.nombre} {obj.usuario.apellido}"
        return None


class CreditoPresencialSerializer(serializers.Serializer):
    """Plan de cuotas para pedidos presenciales a crédito."""

    cantidad_cuotas = serializers.IntegerField(min_value=1)
    interes = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0"),
        help_text="Tasa por período en decimal (0.05 = 5 %).",
    )
    frecuencia_dias = serializers.IntegerField(min_value=1, default=30)
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_interes(self, value):
        if value < 0:
            raise serializers.ValidationError("El interés no puede ser negativo.")
        if value > 1:
            raise serializers.ValidationError(
                "El interés debe expresarse en decimal (ej. 0.05 para 5 %)."
            )
        return value


class CreditoPedidoSerializer(CreditoPresencialSerializer):
    """Mismos campos para registrar crédito sobre un pedido ya creado."""


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
    credito = CreditoPresencialSerializer(required=False)

    def validate(self, data):
        tipo_pago = data.get("tipo_pago")
        usuario = data.get("usuario")
        credito = data.get("credito")

        if tipo_pago == Pedido.TipoPago.CREDITO:
            if not usuario:
                raise serializers.ValidationError(
                    {"usuario": "Es obligatorio para ventas a crédito."}
                )
            if not credito:
                raise serializers.ValidationError(
                    {"credito": "Debe indicar el plan de cuotas."}
                )
        elif credito:
            raise serializers.ValidationError(
                {"credito": 'Solo aplica cuando tipo_pago es "credito".'}
            )
        return data

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
