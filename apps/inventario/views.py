import calendar

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from rest_framework import mixins
from rest_framework import serializers as rest_serializers
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import models, serializers, services


def _add_one_month(fecha):
    year = fecha.year + (1 if fecha.month == 12 else 0)
    month = 1 if fecha.month == 12 else fecha.month + 1
    day = min(fecha.day, calendar.monthrange(year, month)[1])
    return fecha.replace(year=year, month=month, day=day)


class ProtectedDestroyMixin:
    protected_error_message = (
        "No se puede eliminar porque existen registros relacionados."
    )

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": self.protected_error_message},
                status=status.HTTP_400_BAD_REQUEST,
            )


class IngredienteViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    queryset = models.Ingrediente.objects.all()
    serializer_class = serializers.IngredienteSerializer


class ProductoViewSet(ProtectedDestroyMixin, viewsets.ModelViewSet):
    queryset = models.Producto.objects.all()
    serializer_class = serializers.ProductoSerializer


class ProductoIngredienteViewSet(viewsets.ModelViewSet):
    queryset = models.ProductoIngrediente.objects.all()
    serializer_class = serializers.ProductoIngredienteSerializer


class MovimientoIngredienteViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.MovimientoIngrediente.objects.all()
    serializer_class = serializers.MovimientoIngredienteSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            id_ingrediente = serializer.validated_data["id_ingrediente"].id
            ingrediente = models.Ingrediente.objects.select_for_update().get(
                pk=id_ingrediente
            )
            stock_anterior = ingrediente.stock_actual
            cantidad = serializer.validated_data["cantidad"]
            tipo = serializer.validated_data["tipo_movimiento"]

            if tipo == "ENTRADA":
                stock_posterior = stock_anterior + cantidad
                ingrediente.stock_actual = stock_posterior
            elif tipo == "SALIDA":
                if cantidad > stock_anterior:
                    raise rest_serializers.ValidationError(
                        "Stock insuficiente para realizar la salida."
                    )
                stock_posterior = stock_anterior - cantidad
                ingrediente.stock_actual = stock_posterior
            elif tipo == "AJUSTE":
                stock_posterior = cantidad
                ingrediente.stock_actual = stock_posterior
            else:
                raise rest_serializers.ValidationError("tipo_movimiento inválido.")

            ingrediente.save()

            serializer.save(
                stock_anterior=stock_anterior, stock_posterior=stock_posterior
            )


class MovimientoProductoViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.MovimientoProducto.objects.all()
    serializer_class = serializers.MovimientoProductoSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            id_producto = serializer.validated_data["id_producto"].id
            producto = models.Producto.objects.select_for_update().get(pk=id_producto)
            stock_anterior = producto.stock_actual
            cantidad = serializer.validated_data["cantidad"]
            tipo = serializer.validated_data["tipo_movimiento"]
            comentarios = serializer.validated_data.get("comentarios", "")

            if tipo == "ENTRADA":
                stock_posterior = stock_anterior + cantidad
                producto.stock_actual = stock_posterior
            elif tipo == "SALIDA":
                if cantidad > stock_anterior:
                    raise rest_serializers.ValidationError(
                        "Stock insuficiente para realizar la salida."
                    )
                stock_posterior = stock_anterior - cantidad
                producto.stock_actual = stock_posterior
            elif tipo == "AJUSTE":
                stock_posterior = cantidad
                producto.stock_actual = stock_posterior
            else:
                raise rest_serializers.ValidationError("tipo_movimiento inválido.")

            producto.save()

            serializer.save(
                stock_anterior=stock_anterior, stock_posterior=stock_posterior
            )


class ProductoPublicAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        productos = models.Producto.objects.filter(inhabilitado=False)
        serializer = serializers.ProductoSerializer(productos, many=True)
        return Response(serializer.data)


class IngredientePublicAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        ingredientes = models.Ingrediente.objects.all()
        serializer = serializers.IngredientePublicSerializer(ingredientes, many=True)
        return Response(serializer.data)


class ProductoIngredientePublicAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        producto_ingredientes = models.ProductoIngrediente.objects.select_related(
            "id_producto",
            "id_ingrediente",
        ).all()
        serializer = serializers.ProductoIngredienteSerializer(
            producto_ingredientes, many=True
        )
        return Response(serializer.data)


class ProduccionAPIView(APIView):

    def get(self, request):
        producciones = models.Produccion.objects.select_related("id_producto").order_by(
            "-fecha_creacion"
        )
        serializer = serializers.ProduccionSerializer(producciones, many=True)
        return Response(serializer.data)

    def post(self, request):
        id_producto = request.data.get("id_producto")
        cantidad = request.data.get("cantidad_producida")
        fecha_vencimiento = request.data.get("fecha_vencimiento")
        if id_producto is None or cantidad is None or fecha_vencimiento is None:
            return Response(
                {
                    "detail": "id_producto, cantidad_producida y fecha_vencimiento son requeridos."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            id_producto = int(id_producto)
        except Exception:
            return Response(
                {"detail": "id_producto debe ser un entero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cantidad = int(cantidad)
        except Exception:
            return Response(
                {"detail": "cantidad_producida debe ser un entero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fecha_vencimiento_field = rest_serializers.DateTimeField(
            input_formats=["iso-8601", "%Y-%m-%d"]
        )
        try:
            fecha_vencimiento = fecha_vencimiento_field.run_validation(
                fecha_vencimiento
            )
        except rest_serializers.ValidationError:
            return Response(
                {"detail": "fecha_vencimiento debe ser una fecha/hora valida."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            produccion = services.crear_produccion(
                id_producto=id_producto,
                cantidad_producida=cantidad,
                fecha_vencimiento=fecha_vencimiento,
            )
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except models.Producto.DoesNotExist:
            return Response(
                {"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = serializers.ProduccionSerializer(produccion)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProduccionesProximasVencerAPIView(APIView):

    def get(self, request):
        fecha_actual = timezone.localdate()
        fecha_limite = _add_one_month(fecha_actual)
        producciones = (
            models.Produccion.objects.select_related("id_producto")
            .filter(
                fecha_vencimiento__date__gte=fecha_actual,
                fecha_vencimiento__date__lte=fecha_limite,
            )
            .order_by("fecha_vencimiento", "id")
        )
        serializer = serializers.ProduccionSerializer(producciones, many=True)
        return Response(serializer.data)
