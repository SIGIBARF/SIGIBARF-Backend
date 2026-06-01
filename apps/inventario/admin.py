from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from . import models
from . import services


class ProduccionAdminForm(forms.ModelForm):
    class Meta:
        model = models.Produccion
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('id_producto')
        cantidad = cleaned_data.get('cantidad_producida')

        if not self.instance.pk and producto and cantidad:
            relaciones = models.ProductoIngrediente.objects.select_related('id_ingrediente').filter(
                id_producto=producto
            )
            services.validar_stock_produccion(relaciones, cantidad)

        return cleaned_data


@admin.register(models.Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'proveedor', 'stock_actual', 'stock_minimo', 'unidad_medida')


@admin.register(models.Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'precio', 'stock_actual', 'stock_minimo', 'inhabilitado', 'descripcion')


@admin.register(models.ProductoIngrediente)
class ProductoIngredienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_producto', 'id_ingrediente', 'cantidad_ingrediente','porcentaje_ingrediente')


@admin.register(models.Produccion)
class ProduccionAdmin(admin.ModelAdmin):
    form = ProduccionAdminForm
    list_display = ('id', 'id_producto', 'cantidad_producida', 'fecha_creacion', 'fecha_vencimiento')
    readonly_fields = ('fecha_creacion',)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        try:
            produccion = services.crear_produccion(
                id_producto=obj.id_producto_id,
                cantidad_producida=obj.cantidad_producida,
                fecha_vencimiento=obj.fecha_vencimiento,
            )
        except ValidationError as exc:
            message = getattr(exc, 'message', None) or '; '.join(exc.messages)
            self.message_user(request, message, level=messages.ERROR)
            raise

        obj.pk = produccion.pk
        obj.id = produccion.id
        obj.fecha_creacion = produccion.fecha_creacion
        obj.fecha_vencimiento = produccion.fecha_vencimiento
        obj.id_producto = produccion.id_producto
        obj._state.adding = False


@admin.register(models.MovimientoIngrediente)
class MovimientoIngredienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_ingrediente', 'tipo_movimiento', 'cantidad', 'stock_anterior', 'stock_posterior', 'fecha', 'comentarios')


@admin.register(models.MovimientoProducto)
class MovimientoProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_producto', 'tipo_movimiento', 'cantidad', 'stock_anterior', 'stock_posterior', 'fecha', 'comentarios')
