from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.usuarios.models import Usuario
from apps.usuarios.permissions import get_user_role_name
from apps.usuarios.serializers import (
    ChangePasswordSerializer,
    ConfirmResetPasswordSerializer,
    LoginSerializer,
    RegistroSerializer,
    ResetPasswordSerializer,
    UsuarioSerializer,
)
from apps.usuarios.utils import change_user_password, send_reset_password_email


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    rol = get_user_role_name(user)
    if rol:
        refresh['rol'] = rol
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class RegistroView(generics.CreateAPIView):
    serializer_class = RegistroSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'tokens': get_tokens_for_user(user),
                'user': UsuarioSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        return Response(
            {
                'tokens': get_tokens_for_user(user),
                'user': UsuarioSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh:
            return Response(
                {'detail': 'Se requiere el campo refresh.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response(
                {'detail': 'Refresh token inválido o ya revocado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PerfilView(generics.RetrieveUpdateAPIView):
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        user = serializer.save()
        completo = bool(user.telefono.strip() and user.direccion.strip())
        if user.is_perfil_completo != completo:
            user.is_perfil_completo = completo
            user.save(update_fields=['is_perfil_completo'])


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Contraseña actualizada correctamente.'},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        correo = serializer.validated_data['correo']
        user = Usuario.objects.filter(correo__iexact=correo).first()

        if user:
            token_generator = PasswordResetTokenGenerator()
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            send_reset_password_email(user.correo, uidb64, token)

        return Response(
            {
                'detail': 'Si el correo existe en la plataforma, se envió el enlace de restablecimiento.',
            },
            status=status.HTTP_200_OK,
        )


class ConfirmResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        if not self._get_valid_user_from_token(uidb64, token):
            return Response(
                {'detail': 'Token inválido o expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'detail': 'Token válido.'}, status=status.HTTP_200_OK)

    def post(self, request, uidb64, token):
        user = self._get_valid_user_from_token(uidb64, token)
        if not user:
            return Response(
                {'detail': 'Token inválido o expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ConfirmResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_user_password(user, serializer.validated_data['new_password'])
        return Response(
            {'detail': 'Contraseña restablecida correctamente.'},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_user(uidb64):
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            return Usuario.objects.get(pk=uid)
        except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
            return None

    def _get_valid_user_from_token(self, uidb64, token):
        user = self._get_user(uidb64)
        if not user:
            return None
        if not PasswordResetTokenGenerator().check_token(user, token):
            return None
        return user
