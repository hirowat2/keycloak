"""Grupos do usuário (Admin, Master, Tech, Limited)."""
from functools import wraps
from django.core.exceptions import PermissionDenied

def user_in_groups(user, groups: list[str]) -> bool:
    """Retorna True se o usuário estiver em pelo menos um dos grupos."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name__in=groups).exists() or user.is_superuser


def _get_request_from_args(*args, **kwargs):
    """Extrai o objeto request, lidando com assinaturas diferentes de view."""

    for arg in args:
        if hasattr(arg, "user"):
            return arg

    request = kwargs.get("request")
    if hasattr(request, "user"):
        return request

    return None

def groups_required(*group_names):
    """
    Decorator para views: restringe acesso a quem estiver em pelo menos um dos grupos.
    Uso:
        @groups_required("Admin", "Coordenador")
        def minha_view(...):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(*args, **kwargs):
            request = _get_request_from_args(*args, **kwargs)

            if request is None:
                raise PermissionDenied("Requisição não encontrada para validar permissões.")
            if not user_in_groups(request.user, list(group_names)):
                raise PermissionDenied  # ou redireciona para outra página
            return view_func(*args, **kwargs)
        return _wrapped_view
    return decorator
