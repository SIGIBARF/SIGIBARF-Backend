import logging

import resend
from django.conf import settings

from apps.usuarios.models import Rol, Usuario
from apps.usuarios.permissions import ROLE_ADMINISTRADOR, ROLE_CLIENTE, ROLES

logger = logging.getLogger(__name__)


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
