from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academics.models import AnneeUniversitaire, Formation, UE, UP
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, ExamenUPCoefficient, SessionExamen, StatutExamen
from rooms.models import AffectationSalle, Salle


class ExamenStatusTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )
        self.pool = User.objects.create_user(
            username="pool",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2035/2036",
            date_debut=date(2035, 9, 1),
            date_fin=date(2036, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Pharmacie")
        self.ue = UE.objects.create(nom="UE Pharma")
        self.formation.ues.add(self.ue)
        self.ue_secondaire = UE.objects.create(nom="UE Pharma 2")
        self.formation.ues.add(self.ue_secondaire)
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session 1",
        )
        self.salle = Salle.objects.create(nom="A101")
        self.examen = Examen.objects.create(
            session=self.session,
            ue=self.ue,
            date=date(2036, 3, 20),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )

    def test_exam_stays_initie_without_room(self):
        self.assertEqual(self.examen.update_statut(save=False), StatutExamen.INITIE)

    def test_exam_becomes_incomplet_with_room_but_missing_watchers(self):
        AffectationSalle.objects.create(
            examen=self.examen,
            salle=self.salle,
            nb_surveillants_requis=2,
        )
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.statut, StatutExamen.INCOMPLET)

    def test_exam_becomes_complet_when_every_room_quota_is_satisfied(self):
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=self.salle,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=self.pool,
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.statut, StatutExamen.COMPLET)

    def test_exam_stays_incomplet_without_exam_responsable_even_if_room_is_complete(self):
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=self.salle,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=self.pool,
            is_responsable_salle=True,
        )
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.statut, StatutExamen.INCOMPLET)

    def test_exam_stays_incomplet_without_room_responsable_even_if_quota_is_satisfied(self):
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=self.salle,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=self.pool,
        )
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.statut, StatutExamen.INCOMPLET)

    def test_exam_becomes_termine_when_end_time_has_passed_and_structure_is_complete(self):
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=self.salle,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=self.pool,
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        self.examen.date = timezone.localdate() - timedelta(days=1)
        self.examen.save(update_fields=["date"])
        self.assertEqual(self.examen.update_statut(save=False), StatutExamen.TERMINE)

    def test_past_exam_can_become_incomplet_again_after_modification(self):
        AffectationSalle.objects.create(
            examen=self.examen,
            salle=self.salle,
            nb_surveillants_requis=1,
        )
        self.examen.date = timezone.localdate() - timedelta(days=1)
        self.examen.save(update_fields=["date"])
        self.assertEqual(self.examen.update_statut(save=False), StatutExamen.INCOMPLET)

    def test_exam_schedule_update_respects_existing_room_lock_windows(self):
        other_exam = Examen.objects.create(
            session=self.session,
            ue=self.ue_secondaire,
            date=date(2036, 3, 20),
            heure_debut=time(12, 0),
            heure_fin=time(14, 0),
        )
        AffectationSalle.objects.create(
            examen=self.examen,
            salle=self.salle,
            nb_surveillants_requis=1,
            temps_majore=True,
        )
        AffectationSalle.objects.create(
            examen=other_exam,
            salle=self.salle,
            nb_surveillants_requis=1,
        )

        self.examen.heure_fin = time(12, 30)
        with self.assertRaises(ValidationError) as ctx:
            self.examen.full_clean()
        self.assertIn("date", ctx.exception.message_dict)


class ExamCompletionViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_exam_complete",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
            is_staff=True,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2036/2037",
            date_debut=date(2036, 9, 1),
            date_fin=date(2037, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation completion view")
        self.ue = UE.objects.create(nom="UE Completion View")
        self.ue_secondaire = UE.objects.create(nom="UE Completion View 2")
        self.ue_troisieme = UE.objects.create(nom="UE Completion View 3")
        self.default_up = UP.get_default_up()
        self.up_a = UP.objects.create(nom="Biologie")
        self.up_b = UP.objects.create(nom="Physiologie")
        self.up_c = UP.objects.create(nom="Chimie")
        self.formation.ues.add(self.ue, self.ue_secondaire, self.ue_troisieme)
        self.ue_secondaire.ups.add(self.up_a, self.up_b)
        self.ue_troisieme.ups.add(self.up_c)
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session completion view",
        )
        self.examen = Examen.objects.create(
            session=self.session,
            ue=self.ue,
            date=date(2037, 2, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_completion_page_starts_with_no_room_assigned(self):
        response = self.client.get(reverse("exams:exam_complete", args=[self.examen.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucune salle n'est encore affectée à cet examen.")
        self.assertEqual(self.examen.affectations_salles.count(), 0)
        self.assertContains(response, "Responsable d'épreuve non défini")
        self.assertContains(response, "exam-color-dot")
        self.assertContains(response, self.examen.accent_color)
        self.assertContains(response, "exam-overview-card--neutral")

    def test_exam_create_page_displays_creation_title_and_no_delete_button(self):
        response = self.client.get(reverse("exams:exam_create") + f"?session={self.session.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvel examen")
        self.assertNotContains(response, "Modifier l&#x27;examen")
        self.assertNotContains(response, "Supprimer")
        self.assertNotContains(response, "<label class=\"form-label\">Nom</label>", html=False)

    def test_exam_create_page_hides_ues_already_used_in_selected_session(self):
        response = self.client.get(reverse("exams:exam_create") + f"?session={self.session.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            f'<option value="{self.ue.pk}">{self.ue.display_label}</option>',
            html=True,
        )
        self.assertContains(
            response,
            f'<option value="{self.ue_secondaire.pk}">{self.ue_secondaire.display_label}</option>',
            html=True,
        )

    def test_exam_create_page_displays_up_coefficient_fields_for_available_ues(self):
        response = self.client.get(reverse("exams:exam_create") + f"?session={self.session.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Coefficients par UP")
        self.assertContains(response, self.up_a.nom)
        self.assertContains(response, self.up_b.nom)
        self.assertContains(response, self.default_up.nom)
        self.assertContains(
            response,
            f'up_coefficient__{self.ue_secondaire.pk}__{self.up_a.pk}',
        )
        self.assertContains(
            response,
            f'up_coefficient__{self.ue_secondaire.pk}__{self.default_up.pk}',
        )

    def test_exam_create_page_keeps_selected_ue_coefficient_group_visible_on_invalid_submission(self):
        response = self.client.post(
            reverse("exams:exam_create") + f"?session={self.session.pk}",
            {
                "session": str(self.session.pk),
                "ue": str(self.ue_secondaire.pk),
                "date": "",
                "heure_debut": "10:00",
                "heure_fin": "12:00",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-exam-up-coefficients')
        self.assertContains(
            response,
            f'data-ue-group="{self.ue_secondaire.pk}"',
        )
        self.assertContains(
            response,
            f'data-ue-group="{self.ue_troisieme.pk}" hidden',
        )

    def test_exam_create_saves_up_coefficients_for_selected_ue_only(self):
        response = self.client.post(
            reverse("exams:exam_create") + f"?session={self.session.pk}",
            {
                "session": str(self.session.pk),
                "ue": str(self.ue_secondaire.pk),
                "date": "2037-02-12",
                "heure_debut": "10:00",
                "heure_fin": "12:00",
                f"up_coefficient__{self.ue_secondaire.pk}__{self.up_a.pk}": "2",
                f"up_coefficient__{self.ue_secondaire.pk}__{self.up_b.pk}": "5",
                f"up_coefficient__{self.ue_secondaire.pk}__{self.default_up.pk}": "1",
                f"up_coefficient__{self.ue_troisieme.pk}__{self.up_c.pk}": "9",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        created_exam = Examen.objects.get(session=self.session, ue=self.ue_secondaire)
        coefficients = {
            coefficient.up_id: coefficient.coefficient
            for coefficient in created_exam.up_coefficients.all()
        }
        self.assertEqual(coefficients[self.up_a.pk], 2)
        self.assertEqual(coefficients[self.up_b.pk], 5)
        self.assertEqual(coefficients[self.default_up.pk], 1)
        self.assertNotIn(self.up_c.pk, coefficients)

    def test_exam_update_page_displays_update_title_and_delete_button(self):
        response = self.client.get(reverse("exams:exam_update", args=[self.examen.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modifier l'examen")
        self.assertContains(response, "Supprimer")
        self.assertContains(response, f'value="{self.examen.date.isoformat()}"')

    def test_exam_update_page_keeps_current_ue_available(self):
        response = self.client.get(reverse("exams:exam_update", args=[self.examen.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<option value="{self.ue.pk}" selected>{self.ue.display_label}</option>',
            html=True,
        )

    def test_session_create_page_displays_creation_title(self):
        response = self.client.get(reverse("exams:session_create") + f"?formation={self.formation.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvelle session")
        self.assertNotContains(response, "Modifier la session")

    def test_session_update_page_displays_update_title(self):
        response = self.client.get(reverse("exams:session_update", args=[self.session.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modifier la session")

    def test_completion_page_returns_to_exam_list_and_not_exam_detail(self):
        response = self.client.get(reverse("exams:exam_complete", args=[self.examen.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Retour")
        self.assertNotContains(response, "Retour examen")
        self.assertContains(response, reverse("exams:exam_list"))

    def test_completion_page_shows_missing_room_responsable_indicator(self):
        AffectationSalle.objects.create(
            examen=self.examen,
            salle=Salle.objects.create(nom="Salle sans responsable"),
            nb_surveillants_requis=1,
        )
        response = self.client.get(reverse("exams:exam_complete", args=[self.examen.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Responsable de salle non défini")
        self.assertContains(response, "exam-room-card--attention")
        self.assertContains(response, "exam-overview-card--attention")

    def test_completion_page_shows_missing_temps_majore_indicator(self):
        AffectationSalle.objects.create(
            examen=self.examen,
            salle=Salle.objects.create(nom="Salle sans temps majore"),
            nb_surveillants_requis=1,
            temps_majore=False,
        )
        response = self.client.get(reverse("exams:exam_complete", args=[self.examen.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Temps majoré non défini")

    def test_completion_page_displays_inactive_year_flag(self):
        inactive_year = AnneeUniversitaire.objects.create(
            nom="2035/2036",
            date_debut=date(2035, 9, 1),
            date_fin=date(2036, 7, 31),
            is_active=False,
        )
        formation = Formation.objects.create(annee_universitaire=inactive_year, nom="Formation inactive completion")
        formation.ues.add(self.ue)
        session = SessionExamen.objects.create(
            formation=formation,
            nom="Session inactive completion",
        )
        exam = Examen.objects.create(
            session=session,
            ue=self.ue,
            date=date(2036, 2, 11),
            heure_debut=time(10, 0),
            heure_fin=time(12, 0),
        )
        response = self.client.get(reverse("exams:exam_complete", args=[exam.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attention, année inactive")

    def test_completion_page_shows_complete_styles_when_requirements_are_met(self):
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=Salle.objects.create(nom="Salle complete"),
            nb_surveillants_requis=1,
            temps_majore=True,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=self.admin_user,
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        response = self.client.get(reverse("exams:exam_complete", args=[self.examen.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "exam-room-card--complete")
        self.assertContains(response, "exam-overview-card--complete")

    def test_completion_page_displays_up_distribution_from_coefficients(self):
        self.examen.ue = self.ue_secondaire
        self.examen.save(update_fields=["ue"])
        ExamenUPCoefficient.objects.create(examen=self.examen, up=self.up_a, coefficient=1)
        ExamenUPCoefficient.objects.create(examen=self.examen, up=self.up_b, coefficient=2)
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=Salle.objects.create(nom="Salle repartition UP"),
            nb_surveillants_requis=3,
            temps_majore=True,
        )
        teacher_a = User.objects.create_user(
            username="teacher_up_a",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            up=self.up_a,
        )
        teacher_b_1 = User.objects.create_user(
            username="teacher_up_b_1",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            up=self.up_b,
        )
        teacher_b_2 = User.objects.create_user(
            username="teacher_up_b_2",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            up=self.up_b,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=teacher_a,
            is_responsable_general=True,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=teacher_b_1,
            is_responsable_salle=True,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=teacher_b_2,
        )

        response = self.client.get(reverse("exams:exam_complete", args=[self.examen.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Répartition par UP")
        self.assertContains(
            response,
            '<div class="exam-up-distribution__item"><span class="exam-up-distribution__label">Biologie</span><strong>1/1</strong></div>',
            html=True,
        )
        self.assertContains(
            response,
            '<div class="exam-up-distribution__item"><span class="exam-up-distribution__label">Physiologie</span><strong>2/2</strong></div>',
            html=True,
        )
        self.assertContains(
            response,
            '<div class="exam-up-distribution__item exam-up-distribution__item--other"><span class="exam-up-distribution__label">Autres</span><strong>0</strong></div>',
            html=True,
        )

    def test_completion_page_counts_pool_and_unexpected_up_watchers_in_others(self):
        self.examen.ue = self.ue_secondaire
        self.examen.save(update_fields=["ue"])
        ExamenUPCoefficient.objects.create(examen=self.examen, up=self.up_a, coefficient=1)
        ExamenUPCoefficient.objects.create(examen=self.examen, up=self.up_b, coefficient=2)
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=Salle.objects.create(nom="Salle autres UP"),
            nb_surveillants_requis=3,
        )
        teacher_a = User.objects.create_user(
            username="teacher_up_a_other",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            up=self.up_a,
        )
        teacher_c = User.objects.create_user(
            username="teacher_up_c_other",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            up=self.up_c,
        )
        pool_user = User.objects.create_user(
            username="pool_other",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=teacher_a,
            is_responsable_general=True,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=teacher_c,
            is_responsable_salle=True,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=pool_user,
        )

        response = self.client.get(reverse("exams:exam_complete", args=[self.examen.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<div class="exam-up-distribution__item"><span class="exam-up-distribution__label">Biologie</span><strong>1/1</strong></div>',
            html=True,
        )
        self.assertContains(
            response,
            '<div class="exam-up-distribution__item"><span class="exam-up-distribution__label">Physiologie</span><strong>0/2</strong></div>',
            html=True,
        )
        self.assertContains(
            response,
            '<div class="exam-up-distribution__item exam-up-distribution__item--other"><span class="exam-up-distribution__label">Autres</span><strong>2</strong></div>',
            html=True,
        )

    def test_completion_page_counts_default_up_in_autre_row_when_configured(self):
        self.examen.ue = self.ue_secondaire
        self.examen.save(update_fields=["ue"])
        ExamenUPCoefficient.objects.create(examen=self.examen, up=self.up_a, coefficient=1)
        ExamenUPCoefficient.objects.create(examen=self.examen, up=self.default_up, coefficient=1)
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=Salle.objects.create(nom="Salle autre configure"),
            nb_surveillants_requis=2,
        )
        teacher_a = User.objects.create_user(
            username="teacher_up_a_autre",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            up=self.up_a,
        )
        pool_user = User.objects.create_user(
            username="pool_autre_configure",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=teacher_a,
            is_responsable_general=True,
        )
        Surveillance.objects.create(
            affectation_salle=affectation,
            surveillant=pool_user,
            is_responsable_salle=True,
        )

        response = self.client.get(reverse("exams:exam_complete", args=[self.examen.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<div class="exam-up-distribution__item"><span class="exam-up-distribution__label">{self.default_up.nom}</span><strong>1/1</strong></div>',
            html=True,
        )
        self.assertContains(
            response,
            '<div class="exam-up-distribution__item"><span class="exam-up-distribution__label">Biologie</span><strong>1/1</strong></div>',
            html=True,
        )
        self.assertContains(
            response,
            '<div class="exam-up-distribution__item exam-up-distribution__item--other"><span class="exam-up-distribution__label">Autres</span><strong>0</strong></div>',
            html=True,
        )

    def test_room_update_form_displays_recommended_watchers_placeholder_from_capacity(self):
        salle = Salle.objects.create(nom="Salle conseillee", capacite=60)
        affectation = AffectationSalle.objects.create(
            examen=self.examen,
            salle=salle,
            nb_surveillants_requis=2,
        )
        response = self.client.get(
            reverse("exams:exam_room_update", args=[self.examen.pk, affectation.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'placeholder="Conseillé : 3"')


class SessionDeleteAndValidationTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_delete",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
            is_staff=True,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2028/2029",
            date_debut=date(2028, 9, 1),
            date_fin=date(2029, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(
            annee_universitaire=self.year,
            nom="Formation delete",
        )
        self.ue = UE.objects.create(nom="UE Delete")
        self.formation.ues.add(self.ue)
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session protegee",
        )
        Examen.objects.create(
            session=self.session,
            ue=self.ue,
            nom="Exam protege",
            date=date(2029, 2, 10),
            heure_debut=time(9, 0),
            heure_fin=time(10, 0),
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_delete_protected_session_returns_redirect_instead_of_500(self):
        response = self.client.post(
            reverse("exams:session_delete", args=[self.session.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible")
        self.assertTrue(SessionExamen.objects.filter(pk=self.session.pk).exists())

    def test_session_without_dates_is_valid(self):
        session = SessionExamen(
            formation=self.formation,
            nom="Session logique",
        )
        session.full_clean()


class SessionAndExamScopeTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_filters",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
            is_staff=True,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2032/2033",
            date_debut=date(2032, 9, 1),
            date_fin=date(2033, 7, 31),
            is_active=True,
        )
        self.formation_a = Formation.objects.create(annee_universitaire=self.year, nom="DFGSP2")
        self.formation_b = Formation.objects.create(annee_universitaire=self.year, nom="DFASP1")
        self.ue_a = UE.objects.create(nom="Examen Toxicologie")
        self.ue_b = UE.objects.create(nom="Examen Pharmacologie")
        self.formation_a.ues.add(self.ue_a)
        self.formation_b.ues.add(self.ue_b)
        self.session_a = SessionExamen.objects.create(
            formation=self.formation_a,
            nom="Session Janvier",
        )
        self.session_b = SessionExamen.objects.create(
            formation=self.formation_b,
            nom="Session Juin",
        )
        Examen.objects.create(
            session=self.session_a,
            ue=self.ue_a,
            date=date(2033, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        Examen.objects.create(
            session=self.session_b,
            ue=self.ue_b,
            date=date(2033, 6, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_session_list_can_be_scoped_from_a_formation_click(self):
        response = self.client.get(reverse("exams:session_list"), {"formation": str(self.formation_a.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session Janvier")
        self.assertNotContains(response, "Session Juin")
        self.assertContains(response, "Voir toutes les sessions")

    def test_exam_list_displays_selectors_and_selected_scope(self):
        response = self.client.get(
            reverse("exams:exam_list"),
            {
                "formation": str(self.formation_a.pk),
                "session": str(self.session_a.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sélectionnez une formation")
        self.assertContains(response, "Sélectionnez une session")
        self.assertContains(response, "Gérer les salles")
        self.assertContains(response, reverse("rooms:salle_list"))
        self.assertContains(response, "btn--accent")
        self.assertContains(response, "Examen Toxicologie")
        self.assertContains(response, "exam-color-dot")
        self.assertContains(response, self.ue_a.couleur)
        self.assertNotContains(response, "Examen Pharmacologie")

    def test_exam_list_displays_registered_watchers_ratio_and_initiated_placeholder(self):
        ue_extra = UE.objects.create(nom="Examen Botanique")
        self.formation_a.ues.add(ue_extra)
        exam_incomplet = Examen.objects.create(
            session=self.session_a,
            ue=ue_extra,
            date=date(2033, 1, 11),
            heure_debut=time(14, 0),
            heure_fin=time(16, 0),
        )
        affectation = AffectationSalle.objects.create(
            examen=exam_incomplet,
            salle=Salle.objects.create(nom="Salle ratio examens"),
            nb_surveillants_requis=5,
        )
        for index in range(3):
            Surveillance.objects.create(
                affectation_salle=affectation,
                surveillant=User.objects.create_user(
                    username=f"pool_ratio_{index}",
                    password="pass",
                    role=RoleUtilisateur.MEMBRE_POOL,
                ),
            )

        response = self.client.get(
            reverse("exams:exam_list"),
            {
                "formation": str(self.formation_a.pk),
                "session": str(self.session_a.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Examen Toxicologie 0/?")
        self.assertContains(response, "Examen Botanique 3/5")
        self.assertContains(response, "Initié")
        self.assertContains(response, "Incomplet")

    def test_exam_list_applies_status_outline_classes(self):
        ue_complete = UE.objects.create(nom="Examen Complet Liste")
        ue_incomplete = UE.objects.create(nom="Examen Incomplet Liste")
        ue_finished = UE.objects.create(nom="Examen Terminé Liste")
        self.formation_a.ues.add(ue_complete, ue_incomplete)
        self.formation_a.ues.add(ue_finished)

        exam_complete = Examen.objects.create(
            session=self.session_a,
            ue=ue_complete,
            date=date(2033, 1, 12),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        exam_incomplete = Examen.objects.create(
            session=self.session_a,
            ue=ue_incomplete,
            date=date(2033, 1, 13),
            heure_debut=time(14, 0),
            heure_fin=time(16, 0),
        )
        exam_finished = Examen.objects.create(
            session=self.session_a,
            ue=ue_finished,
            date=timezone.localdate() - timedelta(days=1),
            heure_debut=time(8, 0),
            heure_fin=time(9, 0),
        )

        complete_affectation = AffectationSalle.objects.create(
            examen=exam_complete,
            salle=Salle.objects.create(nom="Salle examen complet liste"),
            nb_surveillants_requis=1,
        )
        incomplete_affectation = AffectationSalle.objects.create(
            examen=exam_incomplete,
            salle=Salle.objects.create(nom="Salle examen incomplet liste"),
            nb_surveillants_requis=2,
        )

        Surveillance.objects.create(
            affectation_salle=complete_affectation,
            surveillant=User.objects.create_user(
                username="surveillant_exam_list_complete",
                password="pass",
                role=RoleUtilisateur.MEMBRE_POOL,
            ),
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        Surveillance.objects.create(
            affectation_salle=incomplete_affectation,
            surveillant=User.objects.create_user(
                username="surveillant_exam_list_incomplete",
                password="pass",
                role=RoleUtilisateur.MEMBRE_POOL,
            ),
        )
        finished_affectation = AffectationSalle.objects.create(
            examen=exam_finished,
            salle=Salle.objects.create(nom="Salle examen termine liste"),
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=finished_affectation,
            surveillant=User.objects.create_user(
                username="surveillant_exam_list_finished",
                password="pass",
                role=RoleUtilisateur.MEMBRE_POOL,
            ),
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        exam_finished.refresh_from_db()

        response = self.client.get(
            reverse("exams:exam_list"),
            {
                "formation": str(self.formation_a.pk),
                "session": str(self.session_a.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "entity-row entity-row--complete")
        self.assertContains(response, "entity-row entity-row--attention")
        self.assertContains(response, "entity-row entity-row--finished")

    def test_exam_list_hides_completion_action_for_finished_exam(self):
        ue_finished = UE.objects.create(nom="Examen Clos")
        self.formation_a.ues.add(ue_finished)
        exam_finished = Examen.objects.create(
            session=self.session_a,
            ue=ue_finished,
            date=timezone.localdate() - timedelta(days=1),
            heure_debut=time(8, 0),
            heure_fin=time(9, 0),
        )
        finished_affectation = AffectationSalle.objects.create(
            examen=exam_finished,
            salle=Salle.objects.create(nom="Salle examen clos"),
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=finished_affectation,
            surveillant=User.objects.create_user(
                username="surveillant_exam_finished_hidden_action",
                password="pass",
                role=RoleUtilisateur.MEMBRE_POOL,
            ),
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        exam_finished.refresh_from_db()

        response = self.client.get(
            reverse("exams:exam_list"),
            {
                "formation": str(self.formation_a.pk),
                "session": str(self.session_a.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            f'href="{reverse("exams:exam_complete", args=[exam_finished.pk])}">Compléter</a>',
            html=False,
        )

    def test_exam_list_keeps_last_selected_scope_when_reopened_without_params(self):
        self.client.get(
            reverse("exams:exam_list"),
            {
                "formation": str(self.formation_a.pk),
                "session": str(self.session_a.pk),
            },
        )
        response = self.client.get(reverse("exams:exam_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Examen Toxicologie")
        self.assertContains(response, "Session Janvier")

    def test_exam_list_defaults_to_session_with_most_incomplete_exams(self):
        ue_botanique = UE.objects.create(nom="Examen Botanique")
        self.formation_a.ues.add(ue_botanique)
        Examen.objects.create(
            session=self.session_a,
            ue=ue_botanique,
            date=date(2033, 1, 11),
            heure_debut=time(14, 0),
            heure_fin=time(16, 0),
        )
        response = self.client.get(reverse("exams:exam_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session Janvier")
        self.assertContains(response, "Examen Toxicologie")
        self.assertContains(response, "Examen Botanique")
        self.assertNotContains(response, "Examen Pharmacologie")

    def test_exam_list_defaults_to_session_with_most_exams_when_everything_is_complete(self):
        salle_a = Salle.objects.create(nom="Salle Session A")
        salle_b = Salle.objects.create(nom="Salle Session B")
        surveillant = User.objects.create_user(
            username="pool_scope_complete",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )

        exams = list(Examen.objects.order_by("nom"))
        affectation_a = AffectationSalle.objects.create(
            examen=exams[0],
            salle=salle_a,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=affectation_a,
            surveillant=surveillant,
            is_responsable_general=True,
            is_responsable_salle=True,
        )

        affectation_b = AffectationSalle.objects.create(
            examen=exams[1],
            salle=salle_b,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=affectation_b,
            surveillant=self.teacher_for_complete_exam(),
            is_responsable_general=True,
            is_responsable_salle=True,
        )

        ue_galenique = UE.objects.create(nom="Examen Galénique")
        self.formation_b.ues.add(ue_galenique)
        Examen.objects.create(
            session=self.session_b,
            ue=ue_galenique,
            date=date(2033, 6, 11),
            heure_debut=time(14, 0),
            heure_fin=time(16, 0),
        )
        extra_exam = Examen.objects.get(ue=ue_galenique)
        extra_room = Salle.objects.create(nom="Salle Session B 2")
        extra_affectation = AffectationSalle.objects.create(
            examen=extra_exam,
            salle=extra_room,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(
            affectation_salle=extra_affectation,
            surveillant=User.objects.create_user(
                username="pool_scope_complete_2",
                password="pass",
                role=RoleUtilisateur.MEMBRE_POOL,
            ),
            is_responsable_general=True,
            is_responsable_salle=True,
        )

        response = self.client.get(reverse("exams:exam_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Session Juin")
        self.assertContains(response, "Examen Pharmacologie")
        self.assertContains(response, "Examen Galénique")
        self.assertNotContains(response, "Examen Toxicologie")

    def test_exam_list_defaults_to_latest_session_when_no_exam_exists(self):
        Examen.objects.all().delete()
        SessionExamen.objects.all().delete()
        semester_1 = SessionExamen.objects.create(
            formation=self.formation_a,
            nom="Semestre 1",
        )
        SessionExamen.objects.create(
            formation=self.formation_a,
            nom="Semestre 2",
        )
        latest_session = SessionExamen.objects.create(
            formation=self.formation_a,
            nom="Rattrapages",
        )
        response = self.client.get(reverse("exams:exam_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, latest_session.nom)
        self.assertContains(
            response,
            f'<option value="{latest_session.pk}" selected>{latest_session.nom}</option>',
            html=True,
        )
        self.assertContains(response, "Aucun examen n'est encore rattaché à cette session.")

    def test_exam_list_selecting_formation_defaults_to_session_with_most_incomplete_exams(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation ciblée 1")
        ue_semestre_1 = UE.objects.create(nom="UE Semestre 1")
        ue_semestre_2_a = UE.objects.create(nom="UE Semestre 2 A")
        ue_semestre_2_b = UE.objects.create(nom="UE Semestre 2 B")
        formation.ues.add(ue_semestre_1, ue_semestre_2_a, ue_semestre_2_b)
        semestre_1 = formation.sessions.get(nom="Semestre 1")
        semestre_2 = formation.sessions.get(nom="Semestre 2")

        Examen.objects.create(
            session=semestre_1,
            ue=ue_semestre_1,
            date=date(2033, 1, 15),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        Examen.objects.create(
            session=semestre_2,
            ue=ue_semestre_2_a,
            date=date(2033, 2, 15),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        Examen.objects.create(
            session=semestre_2,
            ue=ue_semestre_2_b,
            date=date(2033, 2, 16),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )

        response = self.client.get(
            reverse("exams:exam_list"),
            {"formation": str(formation.pk), "session": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UE Semestre 2 A")
        self.assertContains(response, "UE Semestre 2 B")
        self.assertNotContains(response, "UE Semestre 1")
        self.assertContains(
            response,
            f'<option value="{semestre_2.pk}" selected>{semestre_2.nom}</option>',
            html=True,
        )

    def test_exam_list_selecting_formation_defaults_to_session_with_most_exams_when_all_complete(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation ciblée 2")
        ue_semestre_1 = UE.objects.create(nom="Complet Semestre 1")
        ue_semestre_2_a = UE.objects.create(nom="Complet Semestre 2 A")
        ue_semestre_2_b = UE.objects.create(nom="Complet Semestre 2 B")
        formation.ues.add(ue_semestre_1, ue_semestre_2_a, ue_semestre_2_b)
        semestre_1 = formation.sessions.get(nom="Semestre 1")
        semestre_2 = formation.sessions.get(nom="Semestre 2")

        exam_semestre_1 = Examen.objects.create(
            session=semestre_1,
            ue=ue_semestre_1,
            date=date(2033, 3, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        exam_semestre_2_a = Examen.objects.create(
            session=semestre_2,
            ue=ue_semestre_2_a,
            date=date(2033, 3, 11),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        exam_semestre_2_b = Examen.objects.create(
            session=semestre_2,
            ue=ue_semestre_2_b,
            date=date(2033, 3, 12),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )

        for index, exam in enumerate([exam_semestre_1, exam_semestre_2_a, exam_semestre_2_b], start=1):
            affectation = AffectationSalle.objects.create(
                examen=exam,
                salle=Salle.objects.create(nom=f"Salle complète {index}"),
                nb_surveillants_requis=1,
            )
            Surveillance.objects.create(
                affectation_salle=affectation,
                surveillant=User.objects.create_user(
                    username=f"surveillant_complet_{index}",
                    password="pass",
                    role=RoleUtilisateur.MEMBRE_POOL,
                ),
                is_responsable_general=True,
                is_responsable_salle=True,
            )

        response = self.client.get(
            reverse("exams:exam_list"),
            {"formation": str(formation.pk), "session": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complet Semestre 2 A")
        self.assertContains(response, "Complet Semestre 2 B")
        self.assertNotContains(response, "Complet Semestre 1")
        self.assertContains(
            response,
            f'<option value="{semestre_2.pk}" selected>{semestre_2.nom}</option>',
            html=True,
        )

    def test_exam_list_selecting_formation_defaults_to_semestre_1_when_no_exam_exists(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation ciblée 3")
        formation.ues.add(UE.objects.create(nom="UE Formation ciblée 3"))
        semestre_1 = formation.sessions.get(nom="Semestre 1")

        response = self.client.get(
            reverse("exams:exam_list"),
            {"formation": str(formation.pk), "session": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<option value="{semestre_1.pk}" selected>{semestre_1.nom}</option>',
            html=True,
        )
        self.assertContains(response, "Aucun examen n'est encore rattaché à cette session.")

    def test_exam_list_displays_pagination_controls(self):
        for index in range(25):
            ue = UE.objects.create(nom=f"Examen pagination {index}")
            self.formation_a.ues.add(ue)
            Examen.objects.create(
                session=self.session_a,
                ue=ue,
                date=date(2033, 1, 11),
                heure_debut=time(9, 0),
                heure_fin=time(11, 0),
            )
        response = self.client.get(
            reverse("exams:exam_list"),
            {
                "formation": str(self.formation_a.pk),
                "session": str(self.session_a.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page")
        self.assertContains(response, "Suivante")

    def test_exam_update_page_displays_delete_button_with_confirmation(self):
        exam = Examen.objects.get(ue=self.ue_a)
        response = self.client.get(reverse("exams:exam_update", args=[exam.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Supprimer")
        self.assertContains(response, "Êtes-vous sûr de vouloir supprimer cet examen ?")
        self.assertContains(response, reverse("exams:exam_delete", args=[exam.pk]))

    def teacher_for_complete_exam(self):
        return User.objects.create_user(
            username="pool_scope_complete_teacher",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )

    def test_default_session_order_is_semesters_then_rattrapages_then_others(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation ordre")
        SessionExamen.objects.filter(formation=formation).delete()
        SessionExamen.objects.create(formation=formation, nom="Session libre")
        SessionExamen.objects.create(formation=formation, nom="Semestre 2")
        SessionExamen.objects.create(formation=formation, nom="Rattrapages")
        SessionExamen.objects.create(formation=formation, nom="Semestre 1")

        ordered_names = list(
            SessionExamen.ordered_queryset(
                SessionExamen.objects.filter(formation=formation)
            ).values_list("nom", flat=True)
        )
        self.assertEqual(
            ordered_names,
            ["Semestre 1", "Semestre 2", "Rattrapages", "Session libre"],
        )


class ExamenValidationTests(TestCase):
    def setUp(self):
        self.year = AnneeUniversitaire.objects.create(
            nom="2031/2032",
            date_debut=date(2031, 9, 1),
            date_fin=date(2032, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(
            annee_universitaire=self.year,
            nom="Formation validation",
        )
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session validation exam",
        )

    def test_ue_must_belong_to_the_session_formation(self):
        ue_outside = UE.objects.create(nom="UE Externe")
        exam = Examen(
            session=self.session,
            ue=ue_outside,
            date=date(2032, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            exam.full_clean()
        self.assertIn("ue", ctx.exception.message_dict)

    def test_end_time_must_be_after_start_time(self):
        ue = UE.objects.create(nom="UE Attachée")
        self.formation.ues.add(ue)
        exam = Examen(
            session=self.session,
            ue=ue,
            date=date(2032, 1, 10),
            heure_debut=time(11, 0),
            heure_fin=time(9, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            exam.full_clean()
        self.assertIn("heure_fin", ctx.exception.message_dict)

    def test_exam_date_must_stay_within_academic_year(self):
        ue = UE.objects.create(nom="UE Bornée")
        self.formation.ues.add(ue)
        exam = Examen(
            session=self.session,
            ue=ue,
            date=date(2032, 8, 1),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            exam.full_clean()
        self.assertIn("date", ctx.exception.message_dict)

    def test_same_session_cannot_have_two_exams_for_the_same_ue(self):
        ue = UE.objects.create(nom="UE Unique")
        self.formation.ues.add(ue)
        Examen.objects.create(
            session=self.session,
            ue=ue,
            date=date(2032, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        duplicate_exam = Examen(
            session=self.session,
            ue=ue,
            date=date(2032, 1, 11),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            duplicate_exam.full_clean()
        self.assertIn("ue", ctx.exception.message_dict)

    def test_exam_name_is_synchronized_with_its_ue_name(self):
        ue = UE.objects.create(nom="UE Synchronisée")
        self.formation.ues.add(ue)
        exam = Examen.objects.create(
            session=self.session,
            ue=ue,
            nom="Valeur ignorée",
            date=date(2032, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        self.assertEqual(exam.nom, "UE Synchronisée")

        ue.nom = "UE Synchronisée mise à jour"
        ue.save()
        exam.refresh_from_db()
        self.assertEqual(exam.nom, "UE Synchronisée mise à jour")
