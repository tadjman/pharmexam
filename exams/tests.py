from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academics.models import AnneeUniversitaire, Formation, UE, UP
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen, StatutExamen
from rooms.models import AffectationSalle, Salle


class ExamenStatusTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="pass", role=RoleUtilisateur.ENSEIGNANT)
        self.pool = User.objects.create_user(username="pool", password="pass", role=RoleUtilisateur.MEMBRE_POOL)
        self.year = AnneeUniversitaire.objects.create(
            nom="2035/2036",
            date_debut=date(2035, 9, 1),
            date_fin=date(2036, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Pharmacie")
        self.ue = UE.objects.create(nom="UE Pharma")
        self.ue.responsables.add(self.teacher)
        self.formation.ues.add(self.ue)
        self.up = UP.objects.create(ue=self.ue, nom="UP Galenique", matiere="MG")
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session 1",
            date_debut=date(2036, 3, 1),
            date_fin=date(2036, 3, 31),
        )
        self.salle = Salle.objects.create(nom="A101", capacite_max=40)
        self.examen = Examen.objects.create(
            session=self.session,
            up=self.up,
            nom="Examen Test",
            date=date(2036, 3, 20),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=30,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.teacher,
        )

    def test_exam_stays_initie_without_completion(self):
        self.assertEqual(self.examen.update_statut(save=False), StatutExamen.INITIE)

    def test_exam_becomes_incomplet_with_partial_completion(self):
        AffectationSalle.objects.create(examen=self.examen, salle=self.salle)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.statut, StatutExamen.INCOMPLET)

    def test_exam_becomes_complet_when_rooms_and_surveillants_are_satisfied(self):
        AffectationSalle.objects.create(examen=self.examen, salle=self.salle)
        Surveillance.objects.create(examen=self.examen, surveillant=self.pool)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.statut, StatutExamen.COMPLET)

    def test_exam_becomes_termine_when_end_time_has_passed(self):
        self.examen.date = timezone.localdate() - timedelta(days=1)
        self.examen.save(update_fields=["date"])
        self.assertEqual(self.examen.update_statut(save=False), StatutExamen.TERMINE)


class SessionDeleteViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_delete", password="pass", role=RoleUtilisateur.SCOLARITE, is_staff=True)
        self.teacher = User.objects.create_user(username="teacher_delete", password="pass", role=RoleUtilisateur.ENSEIGNANT)
        self.year = AnneeUniversitaire.objects.create(
            nom="2028/2029",
            date_debut=date(2028, 9, 1),
            date_fin=date(2029, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation delete")
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session protegee",
            date_debut=date(2029, 2, 1),
            date_fin=date(2029, 2, 28),
        )
        ue = UE.objects.create(nom="UE Delete")
        ue.responsables.add(self.teacher)
        self.formation.ues.add(ue)
        up = UP.objects.create(ue=ue, nom="UP Delete", matiere="DL")
        Examen.objects.create(
            session=self.session,
            up=up,
            nom="Exam protege",
            date=date(2029, 2, 10),
            heure_debut=time(9, 0),
            heure_fin=time(10, 0),
            nb_eleves=10,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.teacher,
        )
        self.client.force_login(self.admin_user)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_delete_protected_session_returns_redirect_instead_of_500(self):
        response = self.client.post(reverse("exams:session_delete", args=[self.session.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible")
        self.assertTrue(SessionExamen.objects.filter(pk=self.session.pk).exists())


class SessionValidationTests(TestCase):
    def setUp(self):
        self.year = AnneeUniversitaire.objects.create(
            nom="2034/2035",
            date_debut=date(2034, 9, 1),
            date_fin=date(2035, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation validation")

    def test_session_end_date_must_be_after_start_date(self):
        session = SessionExamen(
            formation=self.formation,
            nom="Session invalide",
            date_debut=date(2035, 2, 10),
            date_fin=date(2035, 2, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            session.full_clean()
        self.assertIn("date_fin", ctx.exception.message_dict)

    def test_session_must_stay_within_academic_year(self):
        session = SessionExamen(
            formation=self.formation,
            nom="Session hors bornes",
            date_debut=date(2034, 8, 30),
            date_fin=date(2034, 9, 10),
        )
        with self.assertRaises(ValidationError) as ctx:
            session.full_clean()
        self.assertIn("date_debut", ctx.exception.message_dict)


class SessionAndExamFilterTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_filters", password="pass", role=RoleUtilisateur.SCOLARITE, is_staff=True)
        self.teacher = User.objects.create_user(username="teacher_filters", password="pass", role=RoleUtilisateur.ENSEIGNANT)
        self.year = AnneeUniversitaire.objects.create(
            nom="2032/2033",
            date_debut=date(2032, 9, 1),
            date_fin=date(2033, 7, 31),
            is_active=True,
        )
        self.formation_a = Formation.objects.create(annee_universitaire=self.year, nom="DFGSP2")
        self.formation_b = Formation.objects.create(annee_universitaire=self.year, nom="DFASP1")
        ue = UE.objects.create(nom="UE Filtres")
        ue.responsables.add(self.teacher)
        self.formation_a.ues.add(ue)
        self.formation_b.ues.add(ue)
        up_a = UP.objects.create(ue=ue, nom="UP Toxicologie", matiere="TOX")
        up_b = UP.objects.create(ue=ue, nom="UP Pharmacologie", matiere="PHA")
        self.session_a = SessionExamen.objects.create(
            formation=self.formation_a,
            nom="Session Janvier",
            date_debut=date(2033, 1, 1),
            date_fin=date(2033, 1, 31),
        )
        self.session_b = SessionExamen.objects.create(
            formation=self.formation_b,
            nom="Session Juin",
            date_debut=date(2033, 6, 1),
            date_fin=date(2033, 6, 30),
        )
        Examen.objects.create(
            session=self.session_a,
            up=up_a,
            nom="Examen Toxicologie",
            date=date(2033, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=20,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.teacher,
        )
        Examen.objects.create(
            session=self.session_b,
            up=up_b,
            nom="Examen Pharmacologie",
            date=date(2033, 6, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=20,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.teacher,
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

    def test_exam_list_displays_year_formation_and_session_selectors(self):
        response = self.client.get(reverse("exams:exam_list"), {"year": str(self.year.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sélectionnez une année universitaire")
        self.assertContains(response, "Sélectionnez une formation")
        self.assertContains(response, "Sélectionnez une session")
        self.assertNotContains(response, "Afficher")

    def test_exam_list_lists_exams_for_selected_scope(self):
        response = self.client.get(
            reverse("exams:exam_list"),
            {"year": str(self.year.pk), "formation": str(self.formation_a.pk), "session": str(self.session_a.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Examen Toxicologie")
        self.assertNotContains(response, "Examen Pharmacologie")
        self.assertContains(response, "Compléter")

    def test_exam_list_keeps_last_selected_scope_when_reopened_without_params(self):
        self.client.get(
            reverse("exams:exam_list"),
            {"year": str(self.year.pk), "formation": str(self.formation_a.pk), "session": str(self.session_a.pk)},
        )
        response = self.client.get(reverse("exams:exam_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Examen Toxicologie")
        self.assertNotContains(response, "Examen Pharmacologie")
        self.assertContains(response, "Session Janvier")

    def test_exam_list_displays_pagination_controls(self):
        up = UP.objects.get(nom="UP Toxicologie")
        for index in range(25):
            Examen.objects.create(
                session=self.session_a,
                up=up,
                nom=f"Examen pagination {index}",
                date=date(2033, 1, 11),
                heure_debut=time(9, 0),
                heure_fin=time(11, 0),
                nb_eleves=20,
                nb_eleves_tiers_temps=0,
                nb_surveillants_requis=1,
                responsable=self.teacher,
            )
        response = self.client.get(
            reverse("exams:exam_list"),
            {"year": str(self.year.pk), "formation": str(self.formation_a.pk), "session": str(self.session_a.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page")
        self.assertContains(response, "Suivante")


class ExamenValidationMessageTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher_validation_exam", password="pass", role=RoleUtilisateur.ENSEIGNANT)
        self.outsider = User.objects.create_user(username="outsider_validation_exam", password="pass", role=RoleUtilisateur.ENSEIGNANT)
        self.year = AnneeUniversitaire.objects.create(
            nom="2031/2032",
            date_debut=date(2031, 9, 1),
            date_fin=date(2032, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation validation")
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session validation exam",
            date_debut=date(2032, 1, 1),
            date_fin=date(2032, 1, 31),
        )

    def test_responsable_error_is_attached_to_field(self):
        ue = UE.objects.create(nom="UE Validation Exam")
        ue.responsables.add(self.teacher)
        self.formation.ues.add(ue)
        up = UP.objects.create(ue=ue, nom="UP Validation Exam", matiere="VE")
        exam = Examen(
            session=self.session,
            up=up,
            nom="Exam validation field",
            date=date(2032, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=30,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.outsider,
        )
        with self.assertRaises(ValidationError) as ctx:
            exam.full_clean()
        self.assertIn("responsable", ctx.exception.message_dict)

    def test_up_must_belong_to_a_ue_attached_to_the_session_formation(self):
        ue_attached = UE.objects.create(nom="UE Attachée")
        ue_attached.responsables.add(self.teacher)
        self.formation.ues.add(ue_attached)
        ue_outside = UE.objects.create(nom="UE Externe")
        ue_outside.responsables.add(self.teacher)
        up_outside = UP.objects.create(ue=ue_outside, nom="UP Externe", matiere="OUT")
        exam = Examen(
            session=self.session,
            up=up_outside,
            nom="Exam bad formation",
            date=date(2032, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=30,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.teacher,
        )
        with self.assertRaises(ValidationError) as ctx:
            exam.full_clean()
        self.assertIn("up", ctx.exception.message_dict)
