from rest_framework.permissions import SAFE_METHODS, BasePermission

ROLE_CLIENTE = 'Cliente'
ROLE_ADMINISTRADOR = 'Administrador'

ROLES = (
    ROLE_CLIENTE,
    ROLE_ADMINISTRADOR,
)


def get_user_role_name(user) -> str | None:
    
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    rol = getattr(user, 'rol', None)
    if rol is not None:
        return getattr(rol, 'nombre', None)

    return None


def user_has_role(user, *role_names: str) -> bool:
    """Verificación por rol (para vistas, servicios o serializers)."""
    role_name = get_user_role_name(user)
    return role_name in role_names if role_name else False


def user_is_cliente(user) -> bool:
    return user_has_role(user, ROLE_CLIENTE)


def user_is_administrador(user) -> bool:
    return user_has_role(user, ROLE_ADMINISTRADOR)


def _is_staff_or_superuser(user) -> bool:
    return bool(
        user
        and getattr(user, 'is_authenticated', False)
        and (getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False))
    )


class RolePermission(BasePermission):
    role_name = None

    def has_permission(self, request, view):
        if _is_staff_or_superuser(request.user):
            return True
        if not self.role_name:
            return False
        return user_has_role(request.user, self.role_name)


class IsCliente(RolePermission):
    role_name = ROLE_CLIENTE


class IsAdministrador(RolePermission):
    role_name = ROLE_ADMINISTRADOR


class IsClienteOrAdministrador(BasePermission):
    def has_permission(self, request, view):
        if _is_staff_or_superuser(request.user):
            return True
        return user_has_role(request.user, ROLE_CLIENTE, ROLE_ADMINISTRADOR)


class IsAdministradorOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if _is_staff_or_superuser(request.user):
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return user_has_role(request.user, ROLE_CLIENTE, ROLE_ADMINISTRADOR)
        return user_is_administrador(request.user)
