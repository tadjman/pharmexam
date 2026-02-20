from .models import AnneeUniversitaire


def active_year(request):
    """
    Expose active_year dans tous les templates :
    - priorité à request.session["active_year_id"] si présent
    - sinon fallback sur AnneeUniversitaire.is_active=True
    """
    year = None
    year_id = request.session.get("active_year_id")

    if year_id:
        try:
            year = AnneeUniversitaire.objects.filter(pk=year_id).first()
        except Exception:
            year = None

    if year is None:
        year = AnneeUniversitaire.objects.filter(is_active=True).first()
        if year:
            request.session["active_year_id"] = str(year.pk)

    return {"active_year": year}
