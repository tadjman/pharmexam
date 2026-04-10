def active_year(request):
    from .utils import get_active_year

    return {"active_year": get_active_year(request, persist_session=True)}
