from rest_framework import serializers
from .models import Notificacion


class NotificacionSerializer(serializers.ModelSerializer):
    source_type = serializers.CharField(read_only=True)
    source_id = serializers.IntegerField(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = Notificacion
        fields = [
            'id',
            'tipo',
            'tipo_display',
            'mensaje',
            'leida',
            'fecha_generada',
            'fecha_leida',
            'source_type',
            'source_id',
        ]
