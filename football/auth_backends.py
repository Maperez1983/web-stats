from __future__ import annotations

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class CaseInsensitiveModelBackend(ModelBackend):
    """
    Autenticación por username case-insensitive.

    Motivo: en iOS/macOS es frecuente que el teclado ponga la primera letra en mayúscula,
    lo que provoca "credenciales inválidas" aunque la contraseña sea correcta.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        username_field = getattr(UserModel, "USERNAME_FIELD", "username")
        if username is None:
            username = kwargs.get(username_field)
        username = str(username or "").strip()
        if not username or password is None:
            return None

        try:
            user = UserModel._default_manager.get(**{f"{username_field}__iexact": username})
        except UserModel.DoesNotExist:
            # Mitiga timing attacks.
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

