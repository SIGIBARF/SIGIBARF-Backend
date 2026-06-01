from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.test import RequestFactory, TestCase
from django.utils import timezone
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
from apps.usuarios.models import Rol, Usuario
from apps.usuarios.permissions import ROLE_ADMINISTRADOR, ROLE_CLIENTE


def crear_usuarios_prueba():
    rol_cliente = Rol.objects.create(nombre=ROLE_CLIENTE)
    rol_admin = Rol.objects.create(nombre=ROLE_ADMINISTRADOR)
    cliente = Usuario.objects.create_user(
        correo="cliente@example.com",
        password="password123",
        nombre="Cliente",
        apellido="Prueba",
        rol=rol_cliente,
    )
    admin = Usuario.objects.create_user(
        correo="admin@example.com",
        password="password123",
        nombre="Admin",
        apellido="Prueba",
        rol=rol_admin,
    )
    return admin, cliente


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


class InventarioPrivatePermissionTest(APITestCase):

    def setUp(self):
        self.admin, self.cliente = crear_usuarios_prueba()

    def test_endpoint_privado_requiere_autenticacion(self):
        response = self.client.get("/api/inventario/productos/")

        self.assertEqual(response.status_code, 401)

    def test_endpoint_privado_rechaza_cliente(self):
        self.client.force_authenticate(user=self.cliente)

        response = self.client.get("/api/inventario/productos/")

        self.assertEqual(response.status_code, 403)

    def test_endpoint_privado_permite_administrador(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/inventario/productos/")

        self.assertEqual(response.status_code, 200)

    def test_movimientos_producto_permite_listar_con_fecha_datetime(self):
        producto = Producto.objects.create(
            nombre="Producto movimiento",
            precio=Decimal("12000.00"),
            stock_actual=10,
            stock_minimo=2,
        )
        MovimientoProducto.objects.create(
            id_producto=producto,
            tipo_movimiento="ENTRADA",
            cantidad=3,
            stock_anterior=7,
            stock_posterior=10,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/inventario/movimientos-producto/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertIn("T", response.data[0]["fecha"])


class InventarioEndpointRoleMatrixTest(APITestCase):

    def setUp(self):
        self.admin, self.cliente = crear_usuarios_prueba()
        self.ingrediente = Ingrediente.objects.create(
            nombre="Leche",
            proveedor="Proveedor A",
            stock_actual=Decimal("80.00"),
            stock_minimo=Decimal("10.00"),
            unidad_medida="l",
        )
        self.producto = Producto.objects.create(
            nombre="Arequipe",
            precio=Decimal("9000.00"),
            stock_actual=15,
            stock_minimo=3,
        )
        self.producto_inhabilitado = Producto.objects.create(
            nombre="Arequipe viejo",
            precio=Decimal("7000.00"),
            stock_actual=1,
            stock_minimo=1,
            inhabilitado=True,
        )
        self.producto_ingrediente = ProductoIngrediente.objects.create(
            id_producto=self.producto,
            id_ingrediente=self.ingrediente,
            cantidad_ingrediente=Decimal("2.00"),
            porcentaje_ingrediente=Decimal("100.00"),
        )
        self.movimiento_ingrediente = MovimientoIngrediente.objects.create(
            id_ingrediente=self.ingrediente,
            tipo_movimiento="ENTRADA",
            cantidad=Decimal("5.00"),
            stock_anterior=Decimal("75.00"),
            stock_posterior=Decimal("80.00"),
        )
        self.movimiento_producto = MovimientoProducto.objects.create(
            id_producto=self.producto,
            tipo_movimiento="ENTRADA",
            cantidad=4,
            stock_anterior=11,
            stock_posterior=15,
        )
        self.produccion = Produccion.objects.create(
            id_producto=self.producto,
            cantidad_producida=2,
            fecha_vencimiento=timezone.now() + timedelta(days=15),
        )

    def test_admin_lista_todos_los_endpoints_privados(self):
        self.client.force_authenticate(user=self.admin)
        urls = [
            "/api/inventario/ingredientes/",
            "/api/inventario/productos/",
            "/api/inventario/producto-ingredientes/",
            "/api/inventario/movimientos-ingrediente/",
            "/api/inventario/movimientos-producto/",
            "/api/inventario/producciones/",
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_cliente_no_accede_a_endpoints_privados(self):
        self.client.force_authenticate(user=self.cliente)
        urls = [
            "/api/inventario/ingredientes/",
            f"/api/inventario/ingredientes/{self.ingrediente.id}/",
            "/api/inventario/productos/",
            f"/api/inventario/productos/{self.producto.id}/",
            "/api/inventario/producto-ingredientes/",
            f"/api/inventario/producto-ingredientes/{self.producto_ingrediente.id}/",
            "/api/inventario/movimientos-ingrediente/",
            f"/api/inventario/movimientos-ingrediente/{self.movimiento_ingrediente.id}/",
            "/api/inventario/movimientos-producto/",
            f"/api/inventario/movimientos-producto/{self.movimiento_producto.id}/",
            "/api/inventario/producciones/",
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)

    def test_cliente_no_puede_escribir_endpoints_privados(self):
        self.client.force_authenticate(user=self.cliente)
        writes = [
            ("post", "/api/inventario/ingredientes/", {}),
            ("patch", f"/api/inventario/ingredientes/{self.ingrediente.id}/", {}),
            ("delete", f"/api/inventario/ingredientes/{self.ingrediente.id}/", {}),
            ("post", "/api/inventario/productos/", {}),
            ("patch", f"/api/inventario/productos/{self.producto.id}/", {}),
            ("delete", f"/api/inventario/productos/{self.producto.id}/", {}),
            ("post", "/api/inventario/producto-ingredientes/", {}),
            ("patch", f"/api/inventario/producto-ingredientes/{self.producto_ingrediente.id}/", {}),
            ("delete", f"/api/inventario/producto-ingredientes/{self.producto_ingrediente.id}/", {}),
            ("post", "/api/inventario/movimientos-ingrediente/", {}),
            ("patch", f"/api/inventario/movimientos-ingrediente/{self.movimiento_ingrediente.id}/", {}),
            ("delete", f"/api/inventario/movimientos-ingrediente/{self.movimiento_ingrediente.id}/", {}),
            ("post", "/api/inventario/movimientos-producto/", {}),
            ("patch", f"/api/inventario/movimientos-producto/{self.movimiento_producto.id}/", {}),
            ("delete", f"/api/inventario/movimientos-producto/{self.movimiento_producto.id}/", {}),
            ("post", "/api/inventario/producciones/", {}),
        ]

        for method, url, payload in writes:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, payload, format="json")
                self.assertEqual(response.status_code, 403)

    def test_endpoints_publicos_responden_para_anonimo_cliente_y_admin(self):
        escenarios = [None, self.cliente, self.admin]

        for user in escenarios:
            self.client.force_authenticate(user=user)
            with self.subTest(user=getattr(user, "correo", "anonimo")):
                productos = self.client.get("/api/inventario/public/productos/")
                ingredientes = self.client.get("/api/inventario/public/ingredientes/")
                relaciones = self.client.get("/api/inventario/public/producto-ingredientes/")

                self.assertEqual(productos.status_code, 200)
                self.assertEqual(ingredientes.status_code, 200)
                self.assertEqual(relaciones.status_code, 200)
                self.assertEqual([item["id"] for item in productos.data], [self.producto.id])
                self.assertNotIn("proveedor", ingredientes.data[0])
                self.assertEqual(relaciones.data[0]["id_producto"], self.producto.id)
                self.assertEqual(relaciones.data[0]["id_ingrediente"], self.ingrediente.id)


class InventarioEndpointDataCoherenceTest(APITestCase):

    def setUp(self):
        self.admin, self.cliente = crear_usuarios_prueba()
        self.client.force_authenticate(user=self.admin)
        self.ingrediente = Ingrediente.objects.create(
            nombre="Harina",
            proveedor="Proveedor A",
            stock_actual=Decimal("100.00"),
            stock_minimo=Decimal("10.00"),
            unidad_medida="kg",
        )
        self.otro_ingrediente = Ingrediente.objects.create(
            nombre="Huevos",
            proveedor="Proveedor B",
            stock_actual=Decimal("50.00"),
            stock_minimo=Decimal("5.00"),
            unidad_medida="kg",
        )
        self.producto = Producto.objects.create(
            nombre="Pan",
            precio=Decimal("2500.00"),
            stock_actual=20,
            stock_minimo=5,
        )

    def test_crud_ingredientes_admin_mantiene_tabla_coherente(self):
        payload = {
            "nombre": "Mantequilla",
            "proveedor": "Proveedor C",
            "stock_actual": "12.50",
            "stock_minimo": "2.00",
            "unidad_medida": "kg",
        }

        create_response = self.client.post("/api/inventario/ingredientes/", payload, format="json")
        self.assertEqual(create_response.status_code, 201)
        ingrediente = Ingrediente.objects.get(pk=create_response.data["id"])
        self.assertEqual(ingrediente.nombre, payload["nombre"])
        self.assertEqual(ingrediente.stock_actual, Decimal("12.50"))

        patch_response = self.client.patch(
            f"/api/inventario/ingredientes/{ingrediente.id}/",
            {"stock_actual": "15.75", "proveedor": "Proveedor C2"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        ingrediente.refresh_from_db()
        self.assertEqual(ingrediente.stock_actual, Decimal("15.75"))
        self.assertEqual(ingrediente.proveedor, "Proveedor C2")

        delete_response = self.client.delete(f"/api/inventario/ingredientes/{ingrediente.id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Ingrediente.objects.filter(pk=ingrediente.id).exists())

    def test_crud_productos_admin_mantiene_tabla_coherente(self):
        payload = {
            "nombre": "Pan integral",
            "precio": "3200.00",
            "stock_actual": 12,
            "stock_minimo": 2,
            "inhabilitado": False,
            "descripcion": "Producto de prueba",
        }

        create_response = self.client.post("/api/inventario/productos/", payload, format="json")
        self.assertEqual(create_response.status_code, 201)
        producto = Producto.objects.get(pk=create_response.data["id"])
        self.assertEqual(producto.precio, Decimal("3200.00"))
        self.assertEqual(producto.stock_actual, 12)

        patch_response = self.client.patch(
            f"/api/inventario/productos/{producto.id}/",
            {"precio": "3500.00", "stock_actual": 10, "inhabilitado": True},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        producto.refresh_from_db()
        self.assertEqual(producto.precio, Decimal("3500.00"))
        self.assertEqual(producto.stock_actual, 10)
        self.assertTrue(producto.inhabilitado)

        delete_response = self.client.delete(f"/api/inventario/productos/{producto.id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Producto.objects.filter(pk=producto.id).exists())

    def test_crud_producto_ingredientes_admin_mantiene_tabla_coherente(self):
        payload = {
            "id_producto": self.producto.id,
            "id_ingrediente": self.ingrediente.id,
            "cantidad_ingrediente": "1.50",
            "porcentaje_ingrediente": "80.00",
        }

        create_response = self.client.post("/api/inventario/producto-ingredientes/", payload, format="json")
        self.assertEqual(create_response.status_code, 201)
        relacion = ProductoIngrediente.objects.get(pk=create_response.data["id"])
        self.assertEqual(relacion.cantidad_ingrediente, Decimal("1.50"))

        patch_response = self.client.patch(
            f"/api/inventario/producto-ingredientes/{relacion.id}/",
            {"cantidad_ingrediente": "2.25", "porcentaje_ingrediente": "90.00"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        relacion.refresh_from_db()
        self.assertEqual(relacion.cantidad_ingrediente, Decimal("2.25"))
        self.assertEqual(relacion.porcentaje_ingrediente, Decimal("90.00"))

        delete_response = self.client.delete(f"/api/inventario/producto-ingredientes/{relacion.id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(ProductoIngrediente.objects.filter(pk=relacion.id).exists())

    def test_movimientos_ingrediente_admin_actualizan_stock_y_movimientos(self):
        entrada = self.client.post(
            "/api/inventario/movimientos-ingrediente/",
            {
                "id_ingrediente": self.ingrediente.id,
                "tipo_movimiento": "ENTRADA",
                "cantidad": "12.50",
                "comentarios": "Compra",
            },
            format="json",
        )
        self.assertEqual(entrada.status_code, 201)
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal("112.50"))
        self.assertEqual(entrada.data["stock_anterior"], "100.00")
        self.assertEqual(entrada.data["stock_posterior"], "112.50")

        salida = self.client.post(
            "/api/inventario/movimientos-ingrediente/",
            {
                "id_ingrediente": self.ingrediente.id,
                "tipo_movimiento": "SALIDA",
                "cantidad": "10.00",
            },
            format="json",
        )
        self.assertEqual(salida.status_code, 201)
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal("102.50"))
        self.assertEqual(salida.data["stock_anterior"], "112.50")
        self.assertEqual(salida.data["stock_posterior"], "102.50")

        ajuste = self.client.post(
            "/api/inventario/movimientos-ingrediente/",
            {
                "id_ingrediente": self.ingrediente.id,
                "tipo_movimiento": "AJUSTE",
                "cantidad": "77.25",
            },
            format="json",
        )
        self.assertEqual(ajuste.status_code, 201)
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal("77.25"))

        insuficiente = self.client.post(
            "/api/inventario/movimientos-ingrediente/",
            {
                "id_ingrediente": self.ingrediente.id,
                "tipo_movimiento": "SALIDA",
                "cantidad": "999.00",
            },
            format="json",
        )
        self.assertEqual(insuficiente.status_code, 400)
        self.ingrediente.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal("77.25"))

    def test_movimientos_producto_admin_actualizan_stock_y_movimientos(self):
        entrada = self.client.post(
            "/api/inventario/movimientos-producto/",
            {
                "id_producto": self.producto.id,
                "tipo_movimiento": "ENTRADA",
                "cantidad": 5,
                "comentarios": "Ingreso manual",
            },
            format="json",
        )
        self.assertEqual(entrada.status_code, 201)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 25)
        self.assertEqual(entrada.data["stock_anterior"], 20)
        self.assertEqual(entrada.data["stock_posterior"], 25)

        salida = self.client.post(
            "/api/inventario/movimientos-producto/",
            {
                "id_producto": self.producto.id,
                "tipo_movimiento": "SALIDA",
                "cantidad": 8,
            },
            format="json",
        )
        self.assertEqual(salida.status_code, 201)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 17)
        self.assertEqual(salida.data["stock_anterior"], 25)
        self.assertEqual(salida.data["stock_posterior"], 17)

        ajuste = self.client.post(
            "/api/inventario/movimientos-producto/",
            {
                "id_producto": self.producto.id,
                "tipo_movimiento": "AJUSTE",
                "cantidad": 11,
            },
            format="json",
        )
        self.assertEqual(ajuste.status_code, 201)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 11)

        insuficiente = self.client.post(
            "/api/inventario/movimientos-producto/",
            {
                "id_producto": self.producto.id,
                "tipo_movimiento": "SALIDA",
                "cantidad": 999,
            },
            format="json",
        )
        self.assertEqual(insuficiente.status_code, 400)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 11)

    def test_movimientos_admin_son_historiales_no_mutables(self):
        movimiento_ingrediente = MovimientoIngrediente.objects.create(
            id_ingrediente=self.ingrediente,
            tipo_movimiento="ENTRADA",
            cantidad=Decimal("3.00"),
            stock_anterior=Decimal("97.00"),
            stock_posterior=Decimal("100.00"),
        )
        movimiento_producto = MovimientoProducto.objects.create(
            id_producto=self.producto,
            tipo_movimiento="ENTRADA",
            cantidad=2,
            stock_anterior=18,
            stock_posterior=20,
        )
        urls = [
            f"/api/inventario/movimientos-ingrediente/{movimiento_ingrediente.id}/",
            f"/api/inventario/movimientos-producto/{movimiento_producto.id}/",
        ]

        for url in urls:
            with self.subTest(method="get", url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
            with self.subTest(method="patch", url=url):
                response = self.client.patch(url, {"cantidad": 99}, format="json")
                self.assertEqual(response.status_code, 405)
            with self.subTest(method="delete", url=url):
                response = self.client.delete(url)
                self.assertEqual(response.status_code, 405)

        self.ingrediente.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(self.ingrediente.stock_actual, Decimal("100.00"))
        self.assertEqual(self.producto.stock_actual, 20)

    def test_delete_protegido_responde_400_sin_error_500(self):
        MovimientoIngrediente.objects.create(
            id_ingrediente=self.ingrediente,
            tipo_movimiento="ENTRADA",
            cantidad=Decimal("3.00"),
            stock_anterior=Decimal("97.00"),
            stock_posterior=Decimal("100.00"),
        )
        MovimientoProducto.objects.create(
            id_producto=self.producto,
            tipo_movimiento="ENTRADA",
            cantidad=2,
            stock_anterior=18,
            stock_posterior=20,
        )

        ingrediente_response = self.client.delete(f"/api/inventario/ingredientes/{self.ingrediente.id}/")
        producto_response = self.client.delete(f"/api/inventario/productos/{self.producto.id}/")

        self.assertEqual(ingrediente_response.status_code, 400)
        self.assertEqual(producto_response.status_code, 400)
        self.assertTrue(Ingrediente.objects.filter(pk=self.ingrediente.id).exists())
        self.assertTrue(Producto.objects.filter(pk=self.producto.id).exists())

    def test_producciones_admin_actualizan_stock_y_movimientos(self):
        ProductoIngrediente.objects.create(
            id_producto=self.producto,
            id_ingrediente=self.ingrediente,
            cantidad_ingrediente=Decimal("2.50"),
            porcentaje_ingrediente=Decimal("70.00"),
        )
        ProductoIngrediente.objects.create(
            id_producto=self.producto,
            id_ingrediente=self.otro_ingrediente,
            cantidad_ingrediente=Decimal("1.00"),
            porcentaje_ingrediente=Decimal("30.00"),
        )
        fecha_vencimiento = (timezone.now() + timedelta(days=20)).date().isoformat()

        response = self.client.post(
            "/api/inventario/producciones/",
            {
                "id_producto": self.producto.id,
                "cantidad_producida": 4,
                "fecha_vencimiento": fecha_vencimiento,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.producto.refresh_from_db()
        self.ingrediente.refresh_from_db()
        self.otro_ingrediente.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 24)
        self.assertEqual(self.ingrediente.stock_actual, Decimal("90.00"))
        self.assertEqual(self.otro_ingrediente.stock_actual, Decimal("46.00"))
        self.assertEqual(Produccion.objects.count(), 1)
        self.assertEqual(MovimientoIngrediente.objects.count(), 2)
        self.assertEqual(MovimientoProducto.objects.count(), 1)

        list_response = self.client.get("/api/inventario/producciones/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data[0]["id"], response.data["id"])


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
        self.fecha_vencimiento = timezone.now() + timedelta(days=30)

    def test_crear_produccion_actualiza_stock_y_movimientos(self):
        produccion = services.crear_produccion(self.producto.id, 4, self.fecha_vencimiento)

        self.assertEqual(produccion.cantidad_producida, 4)
        self.assertEqual(produccion.fecha_vencimiento, self.fecha_vencimiento)

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
        obj = Produccion(
            id_producto=self.producto,
            cantidad_producida=3,
            fecha_vencimiento=self.fecha_vencimiento,
        )

        model_admin.save_model(request, obj, form=None, change=False)

        self.assertIsNotNone(obj.pk)
        self.assertEqual(Produccion.objects.count(), 1)

        self.azucar.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(self.azucar.stock_actual, Decimal("92.50"))
        self.assertEqual(self.producto.stock_actual, 23)
        self.assertEqual(MovimientoIngrediente.objects.count(), 2)
        self.assertEqual(MovimientoProducto.objects.count(), 1)
