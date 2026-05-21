import logging

import resend
from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from apps.usuarios.models import Rol, Usuario
from apps.usuarios.permissions import ROLE_ADMINISTRADOR, ROLE_CLIENTE, ROLES

logger = logging.getLogger(__name__)


class GoogleAuthError(Exception):
    """Error al validar o procesar el inicio de sesión con Google."""


def ensure_roles():
    """Crea los roles Cliente y Administrador si no existen."""
    for nombre in ROLES:
        Rol.objects.get_or_create(nombre=nombre)


def get_rol_cliente():
    ensure_roles()
    return Rol.objects.get(nombre=ROLE_CLIENTE)


def get_rol_administrador():
    ensure_roles()
    return Rol.objects.get(nombre=ROLE_ADMINISTRADOR)


def create_cliente(*, correo, password, nombre, apellido, **kwargs):
    return Usuario.objects.create_user(
        correo=correo,
        password=password,
        nombre=nombre,
        apellido=apellido,
        rol=get_rol_cliente(),
        **kwargs,
    )


def create_cliente_google(*, correo, nombre, apellido, **kwargs):
    """Cliente registrado vía Google (sin contraseña local)."""
    user = Usuario(
        correo=Usuario.objects.normalize_email(correo),
        nombre=nombre,
        apellido=apellido,
        rol=get_rol_cliente(),
        **kwargs,
    )
    user.set_unusable_password()
    user.save()
    return user


def verify_google_id_token(raw_token: str) -> dict:
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise GoogleAuthError('Inicio con Google no está configurado en el servidor.')
    try:
        return id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            settings.GOOGLE_OAUTH_CLIENT_ID,
        )
    except ValueError as exc:
        raise GoogleAuthError('Token de Google inválido o expirado.') from exc


def _names_from_google_claims(claims: dict) -> tuple[str, str]:
    nombre = (claims.get('given_name') or '').strip()
    apellido = (claims.get('family_name') or '').strip()
    if not nombre and not apellido:
        full_name = (claims.get('name') or '').strip()
        if full_name:
            parts = full_name.split(maxsplit=1)
            nombre = parts[0]
            apellido = parts[1] if len(parts) > 1 else '-'
    if not nombre:
        nombre = (claims.get('email') or 'Usuario').split('@')[0]
    if not apellido:
        apellido = '-'
    return nombre[:100], apellido[:100]


def get_or_create_user_from_google(id_token_raw: str) -> Usuario:
    """
    Valida el id_token de Google Identity Services.
    Si el correo existe, inicia sesión; si no, crea un Cliente.
    """
    claims = verify_google_id_token(id_token_raw)

    if not claims.get('email'):
        raise GoogleAuthError('Google no devolvió un correo válido.')

    if claims.get('email_verified') is not True:
        raise GoogleAuthError('El correo de Google no está verificado.')

    correo = Usuario.objects.normalize_email(claims['email'])
    user = Usuario.objects.filter(correo__iexact=correo).first()

    if user is not None:
        if not user.is_active:
            raise GoogleAuthError('La cuenta está inactiva.')
        return user

    nombre, apellido = _names_from_google_claims(claims)
    return create_cliente_google(correo=correo, nombre=nombre, apellido=apellido)


def create_administrador(*, correo, password, nombre, apellido, **kwargs):
    """Solo para uso interno: cuentas del dueño del negocio."""
    return Usuario.objects.create_user(
        correo=correo,
        password=password,
        nombre=nombre,
        apellido=apellido,
        rol=get_rol_administrador(),
        **kwargs,
    )


def change_user_password(user, new_password):
    user.set_password(new_password)
    user.save(update_fields=['password'])


def send_email(to_email, subject, html_content):
    if not settings.RESEND_API_KEY:
        logger.warning(
            'RESEND_API_KEY no configurada. Correo no enviado a %s. Asunto: %s',
            to_email,
            subject,
        )
        print(f'--- Email (sin Resend) ---\nTo: {to_email}\nSubject: {subject}\n{html_content}\n')
        return None

    resend.api_key = settings.RESEND_API_KEY
    try:
        return resend.Emails.send(
            {
                'from': settings.DEFAULT_FROM_EMAIL,
                'to': [to_email],
                'subject': subject,
                'html': html_content,
            }
        )
    except Exception as exc:
        logger.exception('Error enviando correo a %s: %s', to_email, exc)
        return None


def send_reset_password_email(correo, uidb64, token):
    reset_url = f'{settings.FRONTEND_URL}/reset-password?uid={uidb64}&token={token}'
    html = f"""
    <p>Hola,</p>
    <p>Se solicitó un restablecimiento de contraseña en SIGIBARF.</p>
    <p><a href="{reset_url}">Restablecer contraseña</a></p>
    <p>O copia este enlace: {reset_url}</p>
    <p>Si no enviaste esta solicitud, puedes ignorar este correo.</p>
    """
    send_email(correo, 'Restablecer contraseña - SIGIBARF', html)
