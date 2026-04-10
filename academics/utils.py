from .models import AnneeUniversitaire


def get_active_year(request, *, persist_session=False):
    year_id = request.session.get("active_year_id")
    if year_id:
        year = AnneeUniversitaire.objects.filter(pk=year_id).first()
        if year:
            return year

    year = AnneeUniversitaire.objects.filter(is_active=True).first()
    if year and persist_session:
        request.session["active_year_id"] = str(year.pk)
    return year
