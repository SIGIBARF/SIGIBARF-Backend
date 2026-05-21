from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

import serializers
import services
import models


class IngredienteViewSet(viewsets.ModelViewSet):
    queryset = models.Ingrediente.objects.all()
    serializer_class = serializers.IngredienteSerializer


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = models.Producto.objects.all()
    serializer_class = serializers.ProductoSerializer


class ProductoIngredienteViewSet(viewsets.ModelViewSet):
    queryset = models.ProductoIngrediente.objects.all()
    serializer_class = serializers.ProductoIngredienteSerializer


class MovimientoIngredienteViewSet(viewsets.ModelViewSet):
    queryset = models.MovimientoIngrediente.objects.all()
    serializer_class = serializers.MovimientoIngredienteSerializer


class MovimientoProductoViewSet(viewsets.ModelViewSet):
    queryset = models.MovimientoProducto.objects.all()
    serializer_class = serializers.MovimientoProductoSerializer


class ProduccionAPIView(APIView):
    """Endpoint para crear una producción (lógica en services.crear_produccion)

    POST: {"id_producto": 1, "cantidad_producida": 10}
    GET: lista de producciones (últimas 50)
    """

    def get(self, request):
        producciones = models.Produccion.objects.select_related('id_producto').order_by('-fecha')[:50]
        serializer = serializers.ProduccionSerializer(producciones, many=True)
        return Response(serializer.data)

    def post(self, request):
        id_producto = request.data.get('id_producto')
        cantidad = request.data.get('cantidad_producida')
        if id_producto is None or cantidad is None:
            return Response({'detail': 'id_producto y cantidad_producida son requeridos.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cantidad = int(cantidad)
        except Exception:
            return Response({'detail': 'cantidad_producida debe ser un entero.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            produccion = services.crear_produccion(id_producto=int(id_producto), cantidad_producida=cantidad)
        except ValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except models.Producto.DoesNotExist:
            return Response({'detail': 'Producto no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = serializers.ProduccionSerializer(produccion)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
