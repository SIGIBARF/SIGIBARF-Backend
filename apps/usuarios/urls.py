from django.urls import path

from apps.usuarios.views import (
    ChangePasswordView,
    ClienteDetailView,
    ClienteListView,
    ConfirmResetPasswordView,
    GoogleLoginView,
    HealthView,
    LoginView,
    LogoutView,
    PerfilView,
    RefreshTokenView,
    RegistroView,
    ResetPasswordView,
)

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('auth/register/', RegistroView.as_view(), name='register'),
    path('auth/google/', GoogleLoginView.as_view(), name='google-login'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='token-refresh'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/password-reset/', ResetPasswordView.as_view(), name='password-reset'),
    path(
        'auth/password-reset/confirm/<uidb64>/<token>/',
        ConfirmResetPasswordView.as_view(),
        name='password-reset-confirm',
    ),
    path('me/', PerfilView.as_view(), name='perfil'),
    path('admin/clientes/', ClienteListView.as_view(), name='admin-cliente-list'),
    path('admin/clientes/<int:pk>/', ClienteDetailView.as_view(), name='admin-cliente-detail'),
]
