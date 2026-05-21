from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.usuarios.models import Rol, Usuario

# Formulario al editar un usuario existente
FIELDSETS_EDITAR = (
    ('Acceso', {'fields': ('correo', 'password')}),
    ('Perfil', {'fields': ('nombre', 'apellido', 'telefono', 'direccion', 'rol')}),
    ('Cuenta', {'fields': ('is_active', 'is_perfil_completo')}),
    ('Fechas', {'fields': ('last_login', 'created_at', 'updated_at')}),
)

# Extra solo para superusuarios (equipo técnico)
FIELDSET_DESARROLLO = (
    'Solo desarrollo',
    {
        'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions'),
        'classes': ('collapse',),
        'description': 'Acceso al panel Django. El rol de negocio (Cliente/Administrador) se define arriba en Perfil.',
    },
)

# Formulario al crear usuario
FIELDSETS_CREAR = (
    (
        'Nuevo usuario',
        {
            'classes': ('wide',),
            'fields': (
                'correo',
                'nombre',
                'apellido',
                'rol',
                'password1',
                'password2',
                'is_active',
            ),
        },
    ),
)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ('correo', 'nombre', 'apellido', 'rol', 'is_active')
    list_filter = ('rol', 'is_active', 'is_perfil_completo')
    search_fields = ('correo', 'nombre', 'apellido', 'telefono')
    ordering = ('apellido', 'nombre')
    autocomplete_fields = ('rol',)

    readonly_fields = ('last_login', 'created_at', 'updated_at')
    fieldsets = FIELDSETS_EDITAR
    add_fieldsets = FIELDSETS_CREAR

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        if request.user.is_superuser:
            return self.fieldsets + (FIELDSET_DESARROLLO,)
        return self.fieldsets
