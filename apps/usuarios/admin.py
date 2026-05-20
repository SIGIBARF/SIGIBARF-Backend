from django.contrib import admin

from apps.usuarios.models import Rol, Usuario


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'apellido', 'correo', 'rol', 'telefono')
    list_filter = ('rol',)
    search_fields = ('nombre', 'apellido', 'correo', 'telefono')
    autocomplete_fields = ('rol',)
