from apps.usuarios.models import Rol, Usuario
from apps.usuarios.permissions import ROLE_ADMINISTRADOR, ROLE_CLIENTE, ROLES


def ensure_roles():
    """Crea los roles Cliente y Administrador si no existen."""
    for nombre in ROLES:
        Rol.objects.get_or_create(nombre=nombre)


def get_rol_cliente():
    ensure_roles()
    return Rol.objects.get(nombre=ROLE_CLIENTE)


def get_rol_administrador():
    ensure_roles()
    return Rol.objects.get(nombre=ROLE_ADMINISTRADOR)


def create_cliente(*, correo, password, nombre, apellido, **kwargs):
    return Usuario.objects.create_user(
        correo=correo,
        password=password,
        nombre=nombre,
        apellido=apellido,
        rol=get_rol_cliente(),
        **kwargs,
    )


def create_administrador(*, correo, password, nombre, apellido, **kwargs):
    """Solo para uso interno: cuentas del dueño del negocio."""
    return Usuario.objects.create_user(
        correo=correo,
        password=password,
        nombre=nombre,
        apellido=apellido,
        rol=get_rol_administrador(),
        **kwargs,
    )
