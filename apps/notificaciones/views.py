from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notificacion
from .serializers import NotificacionSerializer
from apps.usuarios.permissions import ROLE_ADMINISTRADOR


class NotificacionViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = NotificacionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Solo los administradores pueden ver las notificaciones
        if not hasattr(user, 'rol') or user.rol.nombre != ROLE_ADMINISTRADOR:
            return Notificacion.objects.none()
        
        # Retorna solo las activas
        return Notificacion.objects.filter(leida=False)

    @action(detail=True, methods=['patch'])
    def resolve(self, request, pk=None):
        notificacion = self.get_object()
        notificacion.resolve()
        return Response({'status': 'Notificación resuelta'})
