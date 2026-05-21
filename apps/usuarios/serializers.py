from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.usuarios.models import Usuario
from apps.usuarios.utils import (
    GoogleAuthError,
    change_user_password,
    create_cliente,
    get_or_create_user_from_google,
)


class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.CharField(source='rol.nombre', read_only=True)

    class Meta:
        model = Usuario
        fields = (
            'id',
            'correo',
            'nombre',
            'apellido',
            'telefono',
            'direccion',
            'rol',
            'is_perfil_completo',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'correo',
            'rol',
            'is_active',
            'created_at',
            'updated_at',
        )


class RegistroSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    direccion = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')

    def validate_correo(self, value):
        if Usuario.objects.filter(correo__iexact=value).exists():
            raise serializers.ValidationError('Ya existe una cuenta con este correo.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Las contraseñas no coinciden.',
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        return create_cliente(password=password, **validated_data)


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            attrs['user'] = get_or_create_user_from_google(attrs['id_token'])
        except GoogleAuthError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs


class LoginSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            username=attrs['correo'],
            password=attrs['password'],
        )
        if user is None:
            raise serializers.ValidationError('Correo o contraseña incorrectos.')
        if not user.is_active:
            raise serializers.ValidationError('La cuenta está inactiva.')
        attrs['user'] = user
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    correo = serializers.EmailField()


class ConfirmResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Las contraseñas no coinciden.',
            })
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Las contraseñas no coinciden.',
            })
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        if not user.check_password(self.validated_data['current_password']):
            raise serializers.ValidationError({
                'current_password': 'La contraseña actual no es correcta.',
            })
        change_user_password(user, self.validated_data['new_password'])
        return user
