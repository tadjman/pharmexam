from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from academics.models import AnneeUniversitaire, Formation, UE, UP
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen


class SurveillanceRulesTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher2", password="pass", role=RoleUtilisateur.ENSEIGNANT)
        self.pool_1 = User.objects.create_user(username="pool_1", password="pass", role=RoleUtilisateur.MEMBRE_POOL)
        self.pool_2 = User.objects.create_user(username="pool_2", password="pass", role=RoleUtilisateur.MEMBRE_POOL)
        self.year = AnneeUniversitaire.objects.create(
            nom="2026/2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation 2")
        self.ue = UE.objects.create(nom="UE Chimie")
        self.ue.responsables.add(self.teacher)
        self.formation.ues.add(self.ue)
        self.up = UP.objects.create(ue=self.ue, nom="UP Analyse", matiere="AN")
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session 2",
            date_debut=date(2026, 11, 1),
            date_fin=date(2026, 11, 30),
        )
        self.exam_1 = Examen.objects.create(
            session=self.session,
            up=self.up,
            nom="Exam 1",
            date=date(2026, 11, 10),
            heure_debut=time(8, 0),
            heure_fin=time(10, 0),
            nb_eleves=20,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.teacher,
        )
        self.exam_2 = Examen.objects.create(
            session=self.session,
            up=self.up,
            nom="Exam 2",
            date=date(2026, 11, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=20,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=2,
            responsable=self.teacher,
        )

    def test_quota_blocks_extra_surveillance(self):
        Surveillance.objects.create(examen=self.exam_1, surveillant=self.pool_1)
        surveillance = Surveillance(examen=self.exam_1, surveillant=self.pool_2)
        with self.assertRaises(ValidationError):
            surveillance.full_clean()

    def test_schedule_conflict_blocks_overlapping_surveillance(self):
        Surveillance.objects.create(examen=self.exam_1, surveillant=self.pool_1)
        surveillance = Surveillance(examen=self.exam_2, surveillant=self.pool_1)
        with self.assertRaises(ValidationError):
            surveillance.full_clean()

    def test_validation_message_is_attached_to_surveillant_field(self):
        Surveillance.objects.create(examen=self.exam_1, surveillant=self.pool_1)
        surveillance = Surveillance(examen=self.exam_1, surveillant=self.pool_2)
        with self.assertRaises(ValidationError) as ctx:
            surveillance.full_clean()
        self.assertIn("surveillant", ctx.exception.message_dict)


class SurveillanceCompletionFlowTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_completion", password="pass", role=RoleUtilisateur.SCOLARITE, is_staff=True)
        self.teacher = User.objects.create_user(username="teacher_completion", password="pass", role=RoleUtilisateur.ENSEIGNANT)
        self.pool = User.objects.create_user(username="pool_completion", password="pass", role=RoleUtilisateur.MEMBRE_POOL)
        self.year = AnneeUniversitaire.objects.create(
            nom="2027/2028",
            date_debut=date(2027, 9, 1),
            date_fin=date(2028, 7, 31),
            is_active=True,
        )
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation completion")
        ue = UE.objects.create(nom="UE Completion")
        ue.responsables.add(self.teacher)
        formation.ues.add(ue)
        up = UP.objects.create(ue=ue, nom="UP Completion", matiere="CP")
        self.session = SessionExamen.objects.create(
            formation=formation,
            nom="Session completion",
            date_debut=date(2028, 1, 1),
            date_fin=date(2028, 1, 31),
        )
        self.exam = Examen.objects.create(
            session=self.session,
            up=up,
            nom="Exam Completion",
            date=date(2028, 1, 15),
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

    def test_delete_surveillance_from_exam_completion(self):
        surveillance = Surveillance.objects.create(examen=self.exam, surveillant=self.pool)
        response = self.client.post(
            reverse("exams:exam_complete", args=[self.exam.pk]),
            {"action": "delete_surveillance", "surveillance_id": str(surveillance.pk)},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inscription surveillance supprimée.")
        self.assertFalse(Surveillance.objects.filter(pk=surveillance.pk).exists())

    def test_legacy_surveillance_route_is_not_public_anymore(self):
        response = self.client.get("/surveillances/")
        self.assertEqual(response.status_code, 404)
