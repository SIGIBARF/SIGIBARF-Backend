from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.test import RequestFactory, TestCase
from rest_framework.test import APITestCase

from apps.inventario import admin as inventario_admin
from apps.inventario import services
from apps.inventario.models import (
    Ingrediente,
    MovimientoIngrediente,
    MovimientoProducto,
    Produccion,
    Producto,
    ProductoIngrediente,
)


class ProductoPublicAPIViewTest(APITestCase):

    def test_lista_solo_productos_habilitados(self):
        producto_habilitado = Producto.objects.create(
            nombre="Producto habilitado",
            precio=Decimal("12000.00"),
            stock_actual=10,
            stock_minimo=2,
            inhabilitado=False,
        )
        Producto.objects.create(
            nombre="Producto inhabilitado",
            precio=Decimal("9000.00"),
            stock_actual=5,
            stock_minimo=1,
            inhabilitado=True,
        )

        response = self.client.get(reverse("public-productos"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], producto_habilitado.id)
        self.assertFalse(response.data[0]["inhabilitado"])


class ProduccionStockTest(TestCase):

    def setUp(self):
        self.azucar = Ingrediente.objects.create(
            nombre="Azucar",
            proveedor="Proveedor A",
            stock_actual=Decimal("100.00"),
            stock_minimo=Decimal("10.00"),
            unidad_medida="kg",
        )
        self.agua = Ingrediente.objects.create(
            nombre="Agua",
            proveedor="Proveedor B",
            stock_actual=Decimal("500.00"),
            stock_minimo=Decimal("50.00"),
            unidad_medida="l",
        )
        self.producto = Producto.objects.create(
            nombre="Gaseosa",
            precio=Decimal("5000.00"),
            stock_actual=20,
            stock_minimo=5,
        )
        ProductoIngrediente.objects.create(
            id_producto=self.producto,
            id_ingrediente=self.azucar,
            cantidad_ingrediente=Decimal("2.50"),
            porcentaje_ingrediente=Decimal("10.00"),
        )
        ProductoIngrediente.objects.create(
            id_producto=self.producto,
            id_ingrediente=self.agua,
            cantidad_ingrediente=Decimal("1.00"),
            porcentaje_ingrediente=Decimal("90.00"),
        )

    def test_crear_produccion_actualiza_stock_y_movimientos(self):
        produccion = services.crear_produccion(self.producto.id, 4)

        self.assertEqual(produccion.cantidad_producida, 4)

        self.azucar.refresh_from_db()
        self.agua.refresh_from_db()
        self.producto.refresh_from_db()

        self.assertEqual(self.azucar.stock_actual, Decimal("90.00"))
        self.assertEqual(self.agua.stock_actual, Decimal("496.00"))
        self.assertEqual(self.producto.stock_actual, 24)
        self.assertEqual(MovimientoIngrediente.objects.count(), 2)
        self.assertEqual(MovimientoProducto.objects.count(), 1)

        movimiento_azucar = MovimientoIngrediente.objects.get(id_ingrediente=self.azucar)
        self.assertEqual(movimiento_azucar.cantidad, Decimal("10.00"))
        self.assertEqual(movimiento_azucar.stock_anterior, Decimal("100.00"))
        self.assertEqual(movimiento_azucar.stock_posterior, Decimal("90.00"))

    def test_admin_crea_produccion_usando_servicio_de_stock(self):
        request = RequestFactory().post("/admin/inventario/produccion/add/")
        model_admin = inventario_admin.ProduccionAdmin(Produccion, AdminSite())
        obj = Produccion(id_producto=self.producto, cantidad_producida=3)

        model_admin.save_model(request, obj, form=None, change=False)

        self.assertIsNotNone(obj.pk)
        self.assertEqual(Produccion.objects.count(), 1)

        self.azucar.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(self.azucar.stock_actual, Decimal("92.50"))
        self.assertEqual(self.producto.stock_actual, 23)
        self.assertEqual(MovimientoIngrediente.objects.count(), 2)
        self.assertEqual(MovimientoProducto.objects.count(), 1)
