def resolve_view(name):
    from . import views

    return getattr(views, name)


def call_view(name, *args, **kwargs):
    return resolve_view(name)(*args, **kwargs)


def view_delegate(name):
    def _wrapped(request, *args, **kwargs):
        return call_view(name, request, *args, **kwargs)

    _wrapped.__name__ = name
    _wrapped.__qualname__ = name
    return _wrapped
