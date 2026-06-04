from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.creditos.notificaciones import check_all_creditos_notifications
from apps.usuarios.permissions import ROLE_ADMINISTRADOR

from .models import Notificacion
from .serializers import NotificacionSerializer


class NotificacionViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = NotificacionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, "rol") or user.rol.nombre != ROLE_ADMINISTRADOR:
            return Notificacion.objects.none()

        return Notificacion.objects.filter(leida=False)

    def list(self, request, *args, **kwargs):
        check_all_creditos_notifications()
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def resolve(self, request, pk=None):
        notificacion = self.get_object()
        notificacion.resolve()
        return Response({"status": "Notificación resuelta"})
