from django.apps import AppConfig


class InventarioConfig(AppConfig):
    name = 'apps.inventario'

    def ready(self):
        import apps.inventario.signals
