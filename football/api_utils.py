from django.http import JsonResponse


def api_ok(payload=None, *, status=200, **extra):
    data = {'ok': True}
    if payload:
        data.update(payload)
    if extra:
        data.update(extra)
    return JsonResponse(data, status=status)


def api_error(message, *, status=400, code='', **extra):
    data = {
        'ok': False,
        'error': str(message or 'Error'),
    }
    if code:
        data['code'] = str(code)
    if extra:
        data.update(extra)
    return JsonResponse(data, status=status)
