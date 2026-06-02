from django.urls import reverse
from rest_framework.test import APITestCase

from apps.usuarios.models import Rol, Usuario
from apps.usuarios.permissions import ROLE_ADMINISTRADOR, ROLE_CLIENTE


class UsuarioPrivatePermissionTest(APITestCase):

    def setUp(self):
        rol_cliente = Rol.objects.create(nombre=ROLE_CLIENTE)
        rol_admin = Rol.objects.create(nombre=ROLE_ADMINISTRADOR)
        self.cliente = Usuario.objects.create_user(
            correo="cliente.usuarios@example.com",
            password="password123",
            nombre="Cliente",
            apellido="Usuarios",
            rol=rol_cliente,
        )
        self.admin = Usuario.objects.create_user(
            correo="admin.usuarios@example.com",
            password="password123",
            nombre="Admin",
            apellido="Usuarios",
            rol=rol_admin,
        )

    def test_endpoint_publico_health_no_requiere_autenticacion(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)

    def test_endpoint_privado_perfil_requiere_autenticacion(self):
        response = self.client.get(reverse("perfil"))

        self.assertEqual(response.status_code, 401)

    def test_endpoint_privado_perfil_permite_cliente(self):
        self.client.force_authenticate(user=self.cliente)

        response = self.client.get(reverse("perfil"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["correo"], self.cliente.correo)

    def test_endpoint_privado_perfil_permite_administrador(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("perfil"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["correo"], self.admin.correo)
