from django.test import TestCase
from apps.inventario.models import (
    Ingrediente,
    Producto,
    ProductoIngrediente
)

class ProductoIngredienteTest(TestCase):

    def setUp(self):
        self.azucar = Ingrediente.objects.create(
            nombre="Azúcar",
            proveedor="Proveedor A",
            stock_actual=100,
            stock_minimo=10,
            unidad_medida="kg"
        )

        self.agua = Ingrediente.objects.create(
            nombre="Agua",
            proveedor="Proveedor B",
            stock_actual=500,
            stock_minimo=50,
            unidad_medida="l"
        )

        self.cocacola = Producto.objects.create(
            nombre="Coca Cola",
            precio=5000,
            stock_actual=20,
            stock_minimo=5
        )

        ProductoIngrediente.objects.create(
            id_producto=self.cocacola,
            id_ingrediente=self.azucar,
            cantidad_producida=100,
            cantidad_ingrediente=10,
            porcentaje_ingrediente=10
        )

        ProductoIngrediente.objects.create(
            id_producto=self.cocacola,
            id_ingrediente=self.agua,
            cantidad_producida=100,
            cantidad_ingrediente=90,
            porcentaje_ingrediente=90
        )

    def test_relaciones_producto(self):

        relaciones = ProductoIngrediente.objects.select_related(
            'id_ingrediente'
        ).filter(
            id_producto=self.cocacola
        )

        self.assertEqual(relaciones.count(), 2)

        for relacion in relaciones:
            print("----- RELACION -----")
            print("ID relación:", relacion.id)

            print("Producto:")
            print("  id:", relacion.id_producto.id)
            print("  nombre:", relacion.id_producto.nombre)

            print("Ingrediente:")
            print("  id:", relacion.id_ingrediente.id)
            print("  nombre:", relacion.id_ingrediente.nombre)
            print("  proveedor:", relacion.id_ingrediente.proveedor)
            print("  stock_actual:", relacion.id_ingrediente.stock_actual)
            print("  unidad:", relacion.id_ingrediente.unidad_medida)

            print("Campos intermedios:")
            print("  cantidad_producida:", relacion.cantidad_producida)
            print("  cantidad_ingrediente:", relacion.cantidad_ingrediente)
            print("  porcentaje:", relacion.porcentaje_ingrediente)