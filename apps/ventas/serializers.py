from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.inventario.models import Producto

from .models import CarritoCompra, Pedido, PedidoProducto, ProductoCarrito

User = get_user_model()

_TIPOS_PAGO_PRESENCIAL = frozenset(
    {
        Pedido.TipoPago.EFECTIVO,
        Pedido.TipoPago.CREDITO,
    }
)


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
        if producto and cantidad:
            if producto.stock_actual < cantidad:
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
            "estado",
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
        total = 0
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
    subtotal_productos = serializers.SerializerMethodField()
    listo_para_pago = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id",
            "tipo_pago",
            "cliente_presencial",
            "coordenadas_lat",
            "coordenadas_lng",
            "direccion_envio",
            "estado_pedido",
            "costo_envio",
            "subtotal_productos",
            "precio_total",
            "aprobado_admin",
            "listo_para_pago",
            "fecha_creacion",
            "id_transaccion_wompi",
            "estado_pago",
            "fecha_pago",
            "productos",
        ]

    def get_subtotal_productos(self, obj):
        return sum(
            (linea.subtotal for linea in obj.pedidoproducto_set.all()),
            Decimal("0.00"),
        )

    def get_listo_para_pago(self, obj):
        return (
            not obj.cliente_presencial
            and obj.aprobado_admin
            and obj.estado_pago == Pedido.EstadoPago.PENDIENTE
            and obj.estado_pedido != Pedido.EstadoPedido.CANCELADO
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


class PedidoCheckoutSerializer(serializers.ModelSerializer):
    tipo_pago = serializers.ChoiceField(
        choices=[
            (Pedido.TipoPago.TARJETA, Pedido.TipoPago.TARJETA.label),
            (Pedido.TipoPago.TRANSFERENCIA, Pedido.TipoPago.TRANSFERENCIA.label),
            (
                Pedido.TipoPago.BILLETERA_DIGITAL,
                Pedido.TipoPago.BILLETERA_DIGITAL.label,
            ),
        ]
    )
    direccion_envio = serializers.CharField(trim_whitespace=False)
    coordenadas_lat = serializers.FloatField(required=False, allow_null=True)
    coordenadas_lng = serializers.FloatField(required=False, allow_null=True)

    class Meta:
        model = Pedido
        fields = [
            "tipo_pago",
            "coordenadas_lat",
            "coordenadas_lng",
            "direccion_envio",
        ]

    def validate_direccion_envio(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "La dirección de envío no puede estar vacía."
            )
        return value

    def validate_coordenadas_lat(self, value):
        if value is not None and not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitud inválida.")
        return value

    def validate_coordenadas_lng(self, value):
        if value is not None and not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitud inválida.")
        return value

    def validate(self, data):
        tipo_pago = data.get("tipo_pago")

        if tipo_pago in _TIPOS_PAGO_PRESENCIAL:
            raise serializers.ValidationError(
                "Los pagos en efectivo o crédito solo están disponibles "
                "para pedidos presenciales gestionados por un administrador."
            )

        user = self.context["request"].user
        try:
            carrito = CarritoCompra.objects.get(
                usuario=user, estado=CarritoCompra.Estado.ACTIVO
            )
        except CarritoCompra.DoesNotExist:
            raise serializers.ValidationError("No tienes un carrito activo.")

        items = carrito.productocarrito_set.select_related("producto").all()
        if not items.exists():
            raise serializers.ValidationError("El carrito está vacío.")

        errores = []
        for item in items:
            if item.cantidad > item.producto.stock_actual:
                errores.append(
                    f"{item.producto.nombre}: "
                    f"solo {item.producto.stock_actual} disponibles."
                )
        if errores:
            raise serializers.ValidationError(
                "Stock insuficiente: " + "; ".join(errores)
            )

        return data


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
        help_text=(
            "Usuario al que se asocia el pedido. "
            "Opcional para clientes walk-in anónimos."
        ),
    )
    items = PedidoAdminItemSerializer(many=True)
    tipo_pago = serializers.ChoiceField(
        choices=[
            (Pedido.TipoPago.EFECTIVO, Pedido.TipoPago.EFECTIVO.label),
            (Pedido.TipoPago.CREDITO, Pedido.TipoPago.CREDITO.label),
        ]
    )
    direccion_envio = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    coordenadas_lat = serializers.FloatField(required=False, allow_null=True)
    coordenadas_lng = serializers.FloatField(required=False, allow_null=True)
    costo_envio = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        default=Decimal("0.00"),
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
                    f"'{producto.nombre}': "
                    f"disponible {producto.stock_actual}, "
                    f"solicitado {item['cantidad']}."
                )
        if errores:
            raise serializers.ValidationError(errores)

        return value

    def validate_coordenadas_lat(self, value):
        if value is not None and not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitud inválida.")
        return value

    def validate_coordenadas_lng(self, value):
        if value is not None and not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitud inválida.")
        return value


class PedidoAprobarSerializer(serializers.Serializer):
    costo_envio = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )


class PedidoEstadoSerializer(serializers.Serializer):
    estado_pedido = serializers.ChoiceField(choices=Pedido.EstadoPedido.choices)

    def validate_estado_pedido(self, value):
        if value == Pedido.EstadoPedido.CANCELADO:
            raise serializers.ValidationError(
                "Para cancelar un pedido use el endpoint de cancelación."
            )
        return value
