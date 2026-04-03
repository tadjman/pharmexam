from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from academics.models import AnneeUniversitaire, Formation
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from rooms.models import AffectationSalle

from .forms import (
    AdminNewUserRoleChoiceForm,
    AdminRoomRegistrationForm,
    ExamCompletionRoomForm,
    ExamForm,
    SelfRoomRegistrationForm,
    SessionForm,
    SurveillanceResponsibilityForm,
)
from .models import Examen, SessionExamen, StatutExamen, build_session_order_expression


DEFAULT_SURVEILLANT_PASSWORD = "Pharmexam123!"


class IsScolariteOrAdminMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or user.is_staff or getattr(user, "role", "") == "SCOLARITE"
        )


def get_active_year(request):
    year_id = request.session.get("active_year_id")
    if year_id:
        return AnneeUniversitaire.objects.filter(pk=year_id).first()
    return AnneeUniversitaire.objects.filter(is_active=True).first()


def build_url(name, **params):
    query = urlencode({key: value for key, value in params.items() if value})
    url = reverse(name)
    return f"{url}?{query}" if query else url


def is_admin_user(user):
    return user.is_authenticated and (
        user.is_superuser or user.is_staff or getattr(user, "role", "") == RoleUtilisateur.SCOLARITE
    )


def build_unique_username(first_name: str, last_name: str, email: str) -> str:
    base = slugify(email.split("@", 1)[0] if email else f"{first_name}.{last_name}") or "surveillant"
    username = base
    suffix = 2
    while User.objects.filter(username=username).exists():
        username = f"{base}{suffix}"
        suffix += 1
    return username


class SessionListView(LoginRequiredMixin, ListView):
    model = SessionExamen
    template_name = "exams/session_list.html"
    context_object_name = "sessions"
    paginate_by = 20

    def get_queryset(self):
        self.active_year = get_active_year(self.request)
        self.formations = Formation.objects.select_related("annee_universitaire").order_by(
            "annee_universitaire__date_debut", "nom"
        )
        self.selected_formation = self.request.GET.get("formation", "").strip()
        self.selected_formation_obj = self.formations.filter(pk=self.selected_formation).first() if self.selected_formation else None
        if not self.selected_formation_obj:
            return SessionExamen.objects.none()

        qs = SessionExamen.objects.select_related("formation", "formation__annee_universitaire").filter(
            formation=self.selected_formation_obj
        )
        return SessionExamen.ordered_queryset(qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = getattr(self, "active_year", None)
        ctx["selected_formation"] = getattr(self, "selected_formation", "")
        ctx["selected_formation_obj"] = getattr(self, "selected_formation_obj", None)
        ctx["new_session_url"] = build_url("exams:session_create", formation=ctx["selected_formation"])
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class SessionCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = SessionExamen
    form_class = SessionForm
    template_name = "exams/session_form.html"

    def dispatch(self, request, *args, **kwargs):
        formation_id = request.GET.get("formation")
        self.selected_formation = Formation.objects.select_related("annee_universitaire").filter(pk=formation_id).first()
        self.active_year = self.selected_formation.annee_universitaire if self.selected_formation else get_active_year(request)
        if not self.active_year and not Formation.objects.exists():
            messages.warning(request, "Créez d'abord une formation avant d'ajouter une session.")
            return redirect("academics:formation_list")
        if self.active_year and not Formation.objects.filter(annee_universitaire=self.active_year).exists():
            messages.warning(request, "Créez d'abord une formation pour cette année universitaire avant d'ajouter une session.")
            return redirect(f"{reverse('academics:formation_list')}?year={self.active_year.pk}")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = self.active_year
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if self.selected_formation:
            initial["formation"] = self.selected_formation.pk
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Session créée.")
        return response

    def get_success_url(self):
        return build_url("exams:session_list", formation=self.object.formation_id)


class SessionUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = SessionExamen
    form_class = SessionForm
    template_name = "exams/session_form.html"

    def get_queryset(self):
        return SessionExamen.objects.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = self.object.formation.annee_universitaire
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Session mise à jour.")
        return response

    def get_success_url(self):
        return build_url("exams:session_list", formation=self.object.formation_id)


class SessionDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = SessionExamen
    template_name = "exams/session_confirm_delete.html"
    success_url = reverse_lazy("exams:session_list")

    def get_queryset(self):
        return SessionExamen.objects.all()

    def form_valid(self, form):
        self.object = self.get_object()
        success_url = build_url("exams:session_list", formation=self.object.formation_id)
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                "Suppression impossible : cette session contient encore des examens.",
            )
            return redirect(success_url)
        messages.success(self.request, "Session supprimée.")
        return redirect(success_url)


class ExamListView(LoginRequiredMixin, ListView):
    model = Examen
    template_name = "exams/exam_list.html"
    context_object_name = "examens"
    paginate_by = 20
    scope_session_key = "exam_scope"

    def _read_scope_value(self, key, stored_scope):
        if key in self.request.GET:
            return self.request.GET.get(key, "").strip()
        return stored_scope.get(key, "")

    def _persist_scope(self):
        self.request.session[self.scope_session_key] = {
            "year": str(self.selected_year.pk) if self.selected_year else "",
            "formation": self.selected_formation,
            "session": self.selected_session,
        }
        self.request.session.modified = True

    def _has_explicit_scope(self):
        return any(key in self.request.GET for key in ("year", "formation", "session"))

    def _has_stored_scope(self, stored_scope):
        return any(stored_scope.get(key) for key in ("year", "formation", "session"))

    def _get_default_scope_for_year(self):
        if not self.selected_year:
            return "", ""

        default_session = (
            SessionExamen.objects.select_related("formation")
            .filter(formation__annee_universitaire=self.selected_year)
            .annotate(
                sort_order=build_session_order_expression(),
                incomplete_exam_count=Count(
                    "examens",
                    filter=Q(examens__statut__in=[StatutExamen.INITIE, StatutExamen.INCOMPLET]),
                    distinct=True,
                ),
                exam_count=Count("examens", distinct=True),
            )
            .order_by(
                "-incomplete_exam_count",
                "-exam_count",
                "-sort_order",
                "-nom",
                "formation__nom",
            )
            .first()
        )
        if not default_session:
            return "", ""
        return str(default_session.formation_id), str(default_session.pk)

    def get_queryset(self):
        self.active_year = get_active_year(self.request)
        self.years = AnneeUniversitaire.objects.order_by("-date_debut", "-date_fin")
        stored_scope = self.request.session.get(self.scope_session_key, {})
        explicit_scope = self._has_explicit_scope()
        stored_scope_present = self._has_stored_scope(stored_scope)
        self.selected_year = None
        selected_year_id = self._read_scope_value("year", stored_scope)
        if selected_year_id:
            self.selected_year = self.years.filter(pk=selected_year_id).first()
        if self.selected_year is None:
            self.selected_year = self.active_year or self.years.first()

        if not self.selected_year:
            self.formations = Formation.objects.none()
            self.sessions = SessionExamen.objects.none()
            self.selected_formation = ""
            self.selected_session = ""
            self.selected_formation_obj = None
            self.selected_session_obj = None
            self.formations_payload = []
            self.sessions_payload = []
            self._persist_scope()
            return Examen.objects.none()

        self.formations = Formation.objects.filter(annee_universitaire=self.selected_year).order_by("nom")
        self.selected_formation = self._read_scope_value("formation", stored_scope)
        self.selected_session = self._read_scope_value("session", stored_scope)
        if not explicit_scope and not stored_scope_present:
            self.selected_formation, self.selected_session = self._get_default_scope_for_year()
        self.formations_payload = [
            {
                "id": str(formation.pk),
                "year_id": str(formation.annee_universitaire_id),
                "label": formation.nom,
            }
            for formation in Formation.objects.select_related("annee_universitaire").order_by(
                "annee_universitaire__date_debut", "nom"
            )
        ]
        all_sessions = SessionExamen.ordered_queryset(
            SessionExamen.objects.select_related("formation", "formation__annee_universitaire").filter(
                formation__annee_universitaire=self.selected_year
            )
        )
        self.sessions_payload = [
            {
                "id": str(session.pk),
                "formation_id": str(session.formation_id),
                "label": session.nom,
            }
            for session in all_sessions
        ]

        selected_session_obj = None
        scope_invalid = False
        if self.selected_formation and not self.formations.filter(pk=self.selected_formation).exists():
            self.selected_formation = ""
            self.selected_session = ""
            scope_invalid = True
        if self.selected_session:
            selected_session_obj = all_sessions.filter(pk=self.selected_session).first()
            if selected_session_obj and not self.selected_formation:
                self.selected_formation = str(selected_session_obj.formation_id)
            elif selected_session_obj is None:
                self.selected_session = ""
                scope_invalid = True

        if not explicit_scope and scope_invalid:
            self.selected_formation, self.selected_session = self._get_default_scope_for_year()

        self.selected_formation_obj = self.formations.filter(pk=self.selected_formation).first() if self.selected_formation else None
        self.sessions = all_sessions.filter(formation_id=self.selected_formation) if self.selected_formation else SessionExamen.objects.none()
        self.selected_session_obj = (
            self.sessions.filter(pk=self.selected_session).first()
            if self.selected_session and self.selected_formation
            else None
        )

        if not self.selected_session_obj:
            self.selected_session = ""
            self._persist_scope()
            return Examen.objects.none()

        qs = Examen.objects.select_related(
            "session",
            "session__formation",
            "ue",
        ).filter(session=self.selected_session_obj)

        for exam in qs:
            exam.update_statut(save=True)

        self._persist_scope()

        return (
            Examen.objects.select_related(
                "session",
                "session__formation",
                "ue",
            )
            .filter(session=self.selected_session_obj)
            .order_by("date", "heure_debut")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_year"] = getattr(self, "active_year", None)
        ctx["years"] = getattr(self, "years", AnneeUniversitaire.objects.none())
        ctx["selected_year"] = getattr(self, "selected_year", None)
        ctx["formations"] = getattr(self, "formations", Formation.objects.none())
        ctx["sessions"] = getattr(self, "sessions", SessionExamen.objects.none())
        ctx["selected_formation"] = getattr(self, "selected_formation", "")
        ctx["selected_session"] = getattr(self, "selected_session", "")
        ctx["selected_formation_obj"] = getattr(self, "selected_formation_obj", None)
        ctx["selected_session_obj"] = getattr(self, "selected_session_obj", None)
        ctx["formations_payload"] = getattr(self, "formations_payload", [])
        ctx["sessions_payload"] = getattr(self, "sessions_payload", [])
        ctx["new_exam_url"] = build_url("exams:exam_create", session=ctx["selected_session"])
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class ExamDetailView(LoginRequiredMixin, DetailView):
    model = Examen
    template_name = "exams/exam_detail.html"
    context_object_name = "examen"

    def get_queryset(self):
        return (
            Examen.objects.select_related("session", "session__formation", "session__formation__annee_universitaire", "ue")
            .prefetch_related("affectations_salles__salle", "affectations_salles__surveillances__surveillant")
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        obj.update_statut(save=True)
        return obj


def completion_metrics(exam: Examen):
    affectations = list(exam.affectations_salles.select_related("salle").prefetch_related("surveillances__surveillant"))
    surveillants_required = sum(a.nb_surveillants_requis for a in affectations)
    surveillants_count = sum(a.surveillances.count() for a in affectations)
    complete_rooms = sum(1 for a in affectations if a.surveillances.count() >= a.nb_surveillants_requis)
    responsable_general = exam.surveillances.filter(is_responsable_general=True).select_related("surveillant").first()
    return {
        "room_count": len(affectations),
        "complete_rooms": complete_rooms,
        "temps_majore_count": sum(1 for a in affectations if a.temps_majore),
        "surveillants_count": surveillants_count,
        "surveillants_required": surveillants_required,
        "surveillants_ok": bool(affectations) and complete_rooms == len(affectations),
        "missing_surveillants": max(0, surveillants_required - surveillants_count),
        "responsable_general": responsable_general,
    }


def build_completion_context(request, exam: Examen, is_admin: bool):
    metrics = completion_metrics(exam)
    current_user_surveillance = None
    if not is_admin:
        current_user_surveillance = exam.surveillances.filter(
            surveillant=request.user
        ).select_related("affectation_salle__salle").first()

    room_rows = []
    affectations = exam.affectations_salles.select_related("salle").prefetch_related("surveillances__surveillant")
    for affectation in affectations:
        surveillances = list(affectation.surveillances.all())
        room_rows.append(
            {
                "affectation": affectation,
                "surveillance_rows": [
                    {
                        "surveillance": surveillance,
                        "can_remove": is_admin or surveillance.surveillant_id == request.user.pk,
                        "can_manage_responsibilities": is_admin,
                    }
                    for surveillance in surveillances
                ],
                "is_locked": affectation.is_registration_locked(),
                "is_full": affectation.is_complete,
                "current_user_surveillance": (
                    current_user_surveillance
                    if current_user_surveillance and current_user_surveillance.affectation_salle_id == affectation.pk
                    else None
                ),
                "room_responsable": next(
                    (surveillance for surveillance in surveillances if surveillance.is_responsable_salle),
                    None,
                ),
            }
        )

    return {
        "examen": exam,
        "metrics": metrics,
        "room_rows": room_rows,
        "current_user_surveillance": current_user_surveillance,
        "is_admin_user": is_admin,
    }


class ExamCompletionMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        self.is_admin = is_admin_user(request.user)
        self.examen = get_object_or_404(
            Examen.objects.select_related(
                "session",
                "session__formation",
                "session__formation__annee_universitaire",
                "ue",
            ).prefetch_related(
                "affectations_salles__salle",
                "affectations_salles__surveillances__surveillant",
            ),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def success_url(self):
        return reverse("exams:exam_complete", args=[self.examen.pk])

    def exam_list_url(self):
        return reverse("exams:exam_list")

    def render_page(self, request, template_name, **extra_context):
        context = build_completion_context(request, self.examen, self.is_admin)
        context.update(
            {
                "back_to_list_url": self.exam_list_url(),
            }
        )
        context.update(extra_context)
        return render(request, template_name, context)

    def get_current_user_surveillance(self, request):
        if self.is_admin:
            return None
        return self.examen.surveillances.filter(
            surveillant=request.user
        ).select_related("affectation_salle__salle").first()

    def deny_if_not_admin(self, request):
        if self.is_admin:
            return None
        messages.error(request, "Action non autorisée.")
        return redirect(self.success_url())

    def _get_or_create_user_from_registration(self, form):
        email = form.cleaned_data["email"].strip().lower()
        first_name = form.cleaned_data["first_name"].strip()
        last_name = form.cleaned_data["last_name"].strip()
        role = form.cleaned_data.get("role", RoleUtilisateur.MEMBRE_POOL)
        user = User.objects.filter(email__iexact=email).order_by("date_joined", "username").first()
        created = False
        if user is None:
            user = User.objects.create_user(
                username=build_unique_username(first_name, last_name, email),
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                password=DEFAULT_SURVEILLANT_PASSWORD,
            )
            created = True
        else:
            updated = False
            if first_name and not user.first_name:
                user.first_name = first_name
                updated = True
            if last_name and not user.last_name:
                user.last_name = last_name
                updated = True
            if updated:
                user.save(update_fields=["first_name", "last_name"])
        return user, created

    def _build_registration_form(self, request, affectation):
        if self.is_admin:
            return AdminRoomRegistrationForm(request.POST, general_available=True, room_available=True)
        return SelfRoomRegistrationForm(
            request.POST,
            general_available=self._is_general_available_for_user(request.user),
            room_available=self._is_room_available_for_user(affectation, request.user),
        )

    def _render_registration_page(self, request, form, affectation, current_user_surveillance):
        general_locked = False
        room_locked = False
        if not self.is_admin:
            general_locked = bool(form.fields.get("is_responsable_general") and form.fields["is_responsable_general"].disabled)
            room_locked = bool(form.fields.get("is_responsable_salle") and form.fields["is_responsable_salle"].disabled)
        return self.render_page(
            request,
            "exams/exam_completion_register.html",
            affectation=affectation,
            form=form,
            room_is_full=affectation.is_complete,
            room_is_locked=affectation.is_registration_locked(),
            already_registered_on_room=(
                current_user_surveillance is not None
                and current_user_surveillance.affectation_salle_id == affectation.pk
            ) if not self.is_admin else False,
            general_responsable_locked=general_locked,
            room_responsable_locked=room_locked,
        )

    def _render_new_user_role_choice_page(self, request, affectation, confirmation_form):
        preview = {
            "first_name": confirmation_form.data.get("first_name") or confirmation_form.initial.get("first_name", ""),
            "last_name": confirmation_form.data.get("last_name") or confirmation_form.initial.get("last_name", ""),
            "email": confirmation_form.data.get("email") or confirmation_form.initial.get("email", ""),
        }
        return self.render_page(
            request,
            "exams/exam_completion_register_new_user.html",
            affectation=affectation,
            confirmation_form=confirmation_form,
            new_user_preview=preview,
        )

    def _save_surveillance(self, request, affectation, user, *, is_responsable_general=False, is_responsable_salle=False):
        surveillance = Surveillance(
            affectation_salle=affectation,
            surveillant=user,
            is_responsable_general=is_responsable_general,
            is_responsable_salle=is_responsable_salle,
        )
        previous_states = {"general": [], "room": []}
        previous_states = self._reassign_responsibilities_if_needed(surveillance)
        surveillance.full_clean()
        surveillance.save()
        return previous_states, surveillance

    def _reassign_responsibilities_if_needed(self, surveillance):
        previous_states = {"general": [], "room": []}
        if not self.is_admin:
            return previous_states
        if surveillance.is_responsable_general:
            qs = Surveillance.objects.filter(
                affectation_salle__examen=surveillance.affectation_salle.examen,
                is_responsable_general=True,
            ).exclude(pk=surveillance.pk)
            previous_states["general"] = list(qs.values_list("pk", flat=True))
            qs.update(is_responsable_general=False)
        if surveillance.is_responsable_salle:
            qs = Surveillance.objects.filter(
                affectation_salle=surveillance.affectation_salle,
                is_responsable_salle=True,
            ).exclude(pk=surveillance.pk)
            previous_states["room"] = list(qs.values_list("pk", flat=True))
            qs.update(is_responsable_salle=False)
        return previous_states

    def _restore_responsibilities(self, previous_states):
        if previous_states.get("general"):
            Surveillance.objects.filter(pk__in=previous_states["general"]).update(is_responsable_general=True)
        if previous_states.get("room"):
            Surveillance.objects.filter(pk__in=previous_states["room"]).update(is_responsable_salle=True)

    def _attach_validation_error(self, form, exc):
        if hasattr(exc, "message_dict"):
            for field, errors in exc.message_dict.items():
                target_field = field if field in form.fields else None
                for error in errors:
                    form.add_error(target_field, error)
            return
        for error in exc.messages:
            form.add_error(None, error)

    def _is_general_available_for_user(self, user):
        current = self.examen.surveillances.filter(is_responsable_general=True).first()
        return current is None or current.surveillant_id == user.pk

    def _is_room_available_for_user(self, affectation, user):
        current = affectation.surveillances.filter(is_responsable_salle=True).first()
        return current is None or current.surveillant_id == user.pk


class ExamCompleteView(ExamCompletionMixin, View):
    template_name = "exams/exam_complete.html"

    def get(self, request, *args, **kwargs):
        return self.render_page(request, self.template_name)


class ExamRoomCreateView(ExamCompletionMixin, View):
    template_name = "exams/exam_completion_room_form.html"

    def get(self, request, *args, **kwargs):
        denied = self.deny_if_not_admin(request)
        if denied:
            return denied
        return self.render_page(
            request,
            self.template_name,
            form=ExamCompletionRoomForm(examen=self.examen),
            page_title="Ajouter une salle",
            submit_label="Ajouter la salle",
        )

    def post(self, request, *args, **kwargs):
        denied = self.deny_if_not_admin(request)
        if denied:
            return denied
        form = ExamCompletionRoomForm(request.POST, examen=self.examen)
        if form.is_valid():
            form.save()
            self.examen.update_statut(save=True)
            messages.success(request, "Salle affectée.")
            return redirect(self.success_url())
        return self.render_page(
            request,
            self.template_name,
            form=form,
            page_title="Ajouter une salle",
            submit_label="Ajouter la salle",
        )


class ExamRoomUpdateView(ExamCompletionMixin, View):
    template_name = "exams/exam_completion_room_form.html"

    def get_affectation(self):
        return get_object_or_404(AffectationSalle, pk=self.kwargs["room_pk"], examen=self.examen)

    def get(self, request, *args, **kwargs):
        denied = self.deny_if_not_admin(request)
        if denied:
            return denied
        self.affectation = self.get_affectation()
        return self.render_page(
            request,
            self.template_name,
            form=ExamCompletionRoomForm(examen=self.examen, instance=self.affectation),
            affectation=self.affectation,
            page_title=f"Modifier la salle {self.affectation.salle.nom}",
            submit_label="Enregistrer",
        )

    def post(self, request, *args, **kwargs):
        denied = self.deny_if_not_admin(request)
        if denied:
            return denied
        self.affectation = self.get_affectation()
        form = ExamCompletionRoomForm(request.POST, examen=self.examen, instance=self.affectation)
        if form.is_valid():
            form.save()
            self.examen.update_statut(save=True)
            messages.success(request, "Affectation salle mise à jour.")
            return redirect(self.success_url())
        return self.render_page(
            request,
            self.template_name,
            form=form,
            affectation=self.affectation,
            page_title=f"Modifier la salle {self.affectation.salle.nom}",
            submit_label="Enregistrer",
        )


class ExamRoomDeleteView(ExamCompletionMixin, View):
    template_name = "exams/exam_completion_room_confirm_delete.html"

    def get_affectation(self):
        return get_object_or_404(AffectationSalle, pk=self.kwargs["room_pk"], examen=self.examen)

    def get(self, request, *args, **kwargs):
        denied = self.deny_if_not_admin(request)
        if denied:
            return denied
        self.affectation = self.get_affectation()
        return self.render_page(
            request,
            self.template_name,
            affectation=self.affectation,
            has_surveillances=self.affectation.surveillances.exists(),
        )

    def post(self, request, *args, **kwargs):
        denied = self.deny_if_not_admin(request)
        if denied:
            return denied
        self.affectation = self.get_affectation()
        if self.affectation.surveillances.exists():
            messages.error(
                request,
                "Suppression impossible : désinscris d'abord tous les surveillants de cette salle.",
            )
            return redirect(self.success_url())
        self.affectation.delete()
        self.examen.update_statut(save=True)
        messages.success(request, "Salle supprimée pour cet examen.")
        return redirect(self.success_url())


class ExamRoomRegisterView(ExamCompletionMixin, View):
    template_name = "exams/exam_completion_register.html"

    def get_affectation(self):
        return get_object_or_404(
            AffectationSalle.objects.select_related("salle", "examen"),
            pk=self.kwargs["room_pk"],
            examen=self.examen,
        )

    def get_form(self, request):
        if self.is_admin:
            return AdminRoomRegistrationForm(general_available=True, room_available=True)
        return SelfRoomRegistrationForm(
            general_available=self._is_general_available_for_user(request.user),
            room_available=self._is_room_available_for_user(self.affectation, request.user),
        )

    def get(self, request, *args, **kwargs):
        self.affectation = self.get_affectation()
        current_user_surveillance = self.get_current_user_surveillance(request)
        return self._render_registration_page(
            request,
            self.get_form(request),
            self.affectation,
            current_user_surveillance,
        )

    def post(self, request, *args, **kwargs):
        self.affectation = self.get_affectation()
        current_user_surveillance = self.get_current_user_surveillance(request)
        if self.is_admin and request.POST.get("confirm_new_user") == "1":
            confirmation_form = AdminNewUserRoleChoiceForm(request.POST)
            if confirmation_form.is_valid():
                user, created = self._get_or_create_user_from_registration(confirmation_form)
                previous_states = {"general": [], "room": []}
                try:
                    previous_states, _ = self._save_surveillance(
                        request,
                        self.affectation,
                        user,
                        is_responsable_general=confirmation_form.cleaned_data.get("is_responsable_general", False),
                        is_responsable_salle=confirmation_form.cleaned_data.get("is_responsable_salle", False),
                    )
                except ValidationError as exc:
                    self._restore_responsibilities(previous_states)
                    self._attach_validation_error(confirmation_form, exc)
                else:
                    if created:
                        messages.success(
                            request,
                            (
                                f"Nouvel utilisateur créé et inscrit : {user.display_full_name} "
                                f"(mot de passe par défaut : {DEFAULT_SURVEILLANT_PASSWORD})."
                            ),
                        )
                    else:
                        messages.success(request, "Utilisateur existant inscrit à la salle.")
                    return redirect(self.success_url())
            return self._render_new_user_role_choice_page(request, self.affectation, confirmation_form)

        form = self._build_registration_form(request, self.affectation)
        if form.is_valid():
            if self.is_admin:
                email = form.cleaned_data["email"].strip().lower()
                existing_user = User.objects.filter(email__iexact=email).order_by("date_joined", "username").first()
                if existing_user is None:
                    confirmation_form = AdminNewUserRoleChoiceForm(
                        initial={
                            "first_name": form.cleaned_data["first_name"].strip(),
                            "last_name": form.cleaned_data["last_name"].strip(),
                            "email": email,
                            "is_responsable_general": form.cleaned_data.get("is_responsable_general", False),
                            "is_responsable_salle": form.cleaned_data.get("is_responsable_salle", False),
                            "role": RoleUtilisateur.MEMBRE_POOL,
                        }
                    )
                    return self._render_new_user_role_choice_page(request, self.affectation, confirmation_form)

            user = request.user
            created = False
            if self.is_admin:
                user, created = self._get_or_create_user_from_registration(form)

            previous_states = {"general": [], "room": []}
            try:
                previous_states, _ = self._save_surveillance(
                    request,
                    self.affectation,
                    user,
                    is_responsable_general=form.cleaned_data.get("is_responsable_general", False),
                    is_responsable_salle=form.cleaned_data.get("is_responsable_salle", False),
                )
            except ValidationError as exc:
                self._restore_responsibilities(previous_states)
                self._attach_validation_error(form, exc)
            else:
                if self.is_admin and created:
                    messages.success(
                        request,
                        (
                            f"Utilisateur créé et inscrit : {user.display_full_name} "
                            f"(mot de passe par défaut : {DEFAULT_SURVEILLANT_PASSWORD})."
                        ),
                    )
                elif self.is_admin:
                    messages.success(request, "Utilisateur inscrit à la salle.")
                else:
                    messages.success(request, "Inscription à la salle enregistrée.")
                return redirect(self.success_url())
        return self._render_registration_page(
            request,
            form,
            self.affectation,
            current_user_surveillance,
        )


class ExamSurveillanceDeleteView(ExamCompletionMixin, View):
    template_name = "exams/exam_completion_surveillance_confirm_delete.html"

    def get_surveillance(self):
        return get_object_or_404(
            Surveillance.objects.select_related("surveillant", "affectation_salle__salle", "affectation_salle__examen"),
            pk=self.kwargs["surveillance_pk"],
            affectation_salle__examen=self.examen,
        )

    def _is_allowed(self, request):
        return self.is_admin or self.surveillance.surveillant_id == request.user.pk

    def get(self, request, *args, **kwargs):
        self.surveillance = self.get_surveillance()
        if not self._is_allowed(request):
            messages.error(request, "Action non autorisée.")
            return redirect(self.success_url())
        return self.render_page(
            request,
            self.template_name,
            surveillance=self.surveillance,
        )

    def post(self, request, *args, **kwargs):
        self.surveillance = self.get_surveillance()
        if not self._is_allowed(request):
            messages.error(request, "Action non autorisée.")
            return redirect(self.success_url())
        self.surveillance.delete()
        self.examen.update_statut(save=True)
        messages.success(request, "Inscription supprimée.")
        return redirect(self.success_url())


class ExamSurveillanceResponsibilityUpdateView(ExamCompletionMixin, View):
    template_name = "exams/exam_completion_responsibility_form.html"

    def get_surveillance(self):
        return get_object_or_404(
            Surveillance.objects.select_related("surveillant", "affectation_salle__salle", "affectation_salle__examen"),
            pk=self.kwargs["surveillance_pk"],
            affectation_salle__examen=self.examen,
        )

    def get(self, request, *args, **kwargs):
        denied = self.deny_if_not_admin(request)
        if denied:
            return denied
        self.surveillance = self.get_surveillance()
        return self.render_page(
            request,
            self.template_name,
            surveillance=self.surveillance,
            form=SurveillanceResponsibilityForm(
                initial={
                    "is_responsable_general": self.surveillance.is_responsable_general,
                    "is_responsable_salle": self.surveillance.is_responsable_salle,
                }
            ),
        )

    def post(self, request, *args, **kwargs):
        denied = self.deny_if_not_admin(request)
        if denied:
            return denied
        self.surveillance = self.get_surveillance()
        form = SurveillanceResponsibilityForm(request.POST)
        if form.is_valid():
            updated_surveillance = self.surveillance
            updated_surveillance.is_responsable_general = form.cleaned_data.get("is_responsable_general", False)
            updated_surveillance.is_responsable_salle = form.cleaned_data.get("is_responsable_salle", False)
            previous_states = {"general": [], "room": []}
            try:
                previous_states = self._reassign_responsibilities_if_needed(updated_surveillance)
                updated_surveillance.full_clean()
                updated_surveillance.save()
            except ValidationError as exc:
                self._restore_responsibilities(previous_states)
                self._attach_validation_error(form, exc)
            else:
                messages.success(request, "Responsabilités mises à jour.")
                return redirect(self.success_url())
        return self.render_page(
            request,
            self.template_name,
            surveillance=self.surveillance,
            form=form,
        )


class ExamCreateView(LoginRequiredMixin, IsScolariteOrAdminMixin, CreateView):
    model = Examen
    form_class = ExamForm
    template_name = "exams/exam_form.html"

    def dispatch(self, request, *args, **kwargs):
        session_id = request.GET.get("session")
        self.preselected_session = SessionExamen.objects.select_related("formation", "formation__annee_universitaire").filter(
            pk=session_id
        ).first() if session_id else None
        year_scope = self.preselected_session.formation.annee_universitaire if self.preselected_session else get_active_year(request)
        if not year_scope and not SessionExamen.objects.exists():
            messages.warning(request, "Créez d'abord une session avant d'initier un examen.")
            return redirect("exams:session_list")
        if year_scope and not SessionExamen.objects.filter(formation__annee_universitaire=year_scope).exists():
            messages.warning(request, "Créez d'abord une session pour cette année universitaire avant d'initier un examen.")
            return redirect("exams:exam_list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        year_scope = (
            self.preselected_session.formation.annee_universitaire
            if getattr(self, "preselected_session", None)
            else get_active_year(self.request)
        )
        kwargs["active_year"] = year_scope
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if getattr(self, "preselected_session", None):
            initial["session"] = self.preselected_session.pk
        return initial

    def form_valid(self, form):
        form.instance.statut = StatutExamen.INITIE
        response = super().form_valid(form)
        self.object.update_statut(save=True)
        messages.success(self.request, "Examen créé (statut : INITIÉ).")
        return response

    def get_success_url(self):
        return build_url(
            "exams:exam_list",
            year=self.object.session.formation.annee_universitaire_id,
            formation=self.object.session.formation_id,
            session=self.object.session_id,
        )


class ExamUpdateView(LoginRequiredMixin, IsScolariteOrAdminMixin, UpdateView):
    model = Examen
    form_class = ExamForm
    template_name = "exams/exam_form.html"

    def get_queryset(self):
        return Examen.objects.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["active_year"] = self.object.session.formation.annee_universitaire
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.update_statut(save=True)
        messages.success(self.request, "Examen mis à jour.")
        return response

    def get_success_url(self):
        return build_url(
            "exams:exam_list",
            year=self.object.session.formation.annee_universitaire_id,
            formation=self.object.session.formation_id,
            session=self.object.session_id,
        )


class ExamDeleteView(LoginRequiredMixin, IsScolariteOrAdminMixin, DeleteView):
    model = Examen
    template_name = "exams/exam_confirm_delete.html"
    success_url = reverse_lazy("exams:exam_list")

    def get_queryset(self):
        return Examen.objects.all()

    def form_valid(self, form):
        self.object = self.get_object()
        success_url = build_url(
            "exams:exam_list",
            year=self.object.session.formation.annee_universitaire_id,
            formation=self.object.session.formation_id,
            session=self.object.session_id,
        )
        self.object.delete()
        messages.success(self.request, "Examen supprimé.")
        return redirect(success_url)
