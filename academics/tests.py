from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from accounts.models import RoleUtilisateur, User
from exams.models import Examen, SessionExamen

from .models import AnneeUniversitaire, UE, UP


class AcademicYearPermissionTests(TestCase):
    def setUp(self):
        self.scolarite = User.objects.create_user(
            username="scolarite_user",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
        )
        self.teacher = User.objects.create_user(
            username="teacher_user",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )

    def test_non_scolarite_user_cannot_access_year_creation(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("academics:annee_create"))
        self.assertEqual(response.status_code, 403)

    def test_scolarite_user_can_access_year_creation(self):
        self.client.force_login(self.scolarite)
        response = self.client.get(reverse("academics:annee_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Année universitaire")


class ActiveYearMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="middleware_user",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
        )

    def test_authenticated_user_without_active_year_is_redirected_to_year_list(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("academics:annee_list"))

    def test_existing_active_year_is_loaded_into_session(self):
        year = AnneeUniversitaire.objects.create(
            nom="2026/2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get("active_year_id"), str(year.pk))


class ActiveYearSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="active_year_user",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
        )
        self.year_one = AnneeUniversitaire.objects.create(
            nom="2025/2026",
            date_debut=date(2025, 9, 1),
            date_fin=date(2026, 7, 31),
            is_active=True,
        )
        self.year_two = AnneeUniversitaire.objects.create(
            nom="2026/2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=False,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_year_id"] = str(self.year_one.pk)
        session.save()

    def test_set_active_year_switches_flags_and_session(self):
        response = self.client.post(
            reverse("academics:annee_set_active", args=[self.year_two.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.year_one.refresh_from_db()
        self.year_two.refresh_from_db()
        self.assertFalse(self.year_one.is_active)
        self.assertTrue(self.year_two.is_active)
        self.assertEqual(self.client.session.get("active_year_id"), str(self.year_two.pk))
        self.assertContains(response, "Année active définie")

    def test_non_scolarite_user_cannot_set_active_year(self):
        teacher = User.objects.create_user(
            username="teacher_active_year_denied",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )
        self.client.force_login(teacher)
        response = self.client.post(
            reverse("academics:annee_set_active", args=[self.year_two.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.year_one.refresh_from_db()
        self.year_two.refresh_from_db()
        self.assertTrue(self.year_one.is_active)
        self.assertFalse(self.year_two.is_active)
        self.assertContains(response, "Action non autorisée")

    def test_saving_active_year_deactivates_previous_one(self):
        self.year_two.is_active = True
        self.year_two.save()
        self.year_one.refresh_from_db()
        self.year_two.refresh_from_db()
        self.assertFalse(self.year_one.is_active)
        self.assertTrue(self.year_two.is_active)


class UEUPViewsTests(TestCase):
    def setUp(self):
        self.scolarite = User.objects.create_user(
            username="scolarite_ue_up",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
        )
        self.teacher = User.objects.create_user(
            username="teacher_ue_up",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2027/2028",
            date_debut=date(2027, 9, 1),
            date_fin=date(2028, 7, 31),
            is_active=True,
        )
        self.client.force_login(self.scolarite)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_scolarite_user_can_create_ue(self):
        response = self.client.post(
            reverse("academics:ue_create"),
            {"nom": "UE Biochimie", "responsables": [str(self.teacher.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UE.objects.filter(nom="UE Biochimie").exists())
        self.assertContains(response, "UE créée.")

    def test_scolarite_user_can_create_up(self):
        ue = UE.objects.create(nom="UE Pharmacie")
        response = self.client.post(
            reverse("academics:up_create"),
            {
                "ue": str(ue.pk),
                "nom": "UP Galénique",
                "matiere": "GAL",
                "responsables": [str(self.teacher.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UP.objects.filter(nom="UP Galénique", ue=ue).exists())
        self.assertContains(response, "UP créée.")

    def test_up_delete_is_blocked_when_linked_to_exam(self):
        ue = UE.objects.create(nom="UE Delete")
        ue.responsables.add(self.teacher)
        up = UP.objects.create(ue=ue, nom="UP Delete", matiere="DEL")
        session = SessionExamen.objects.create(
            annee_universitaire=self.year,
            nom="Session liée",
            date_debut=date(2028, 1, 1),
            date_fin=date(2028, 1, 31),
        )
        Examen.objects.create(
            session=session,
            up=up,
            nom="Exam lié",
            date=date(2028, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=10,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.teacher,
        )
        response = self.client.post(reverse("academics:up_delete", args=[up.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible")
        self.assertTrue(UP.objects.filter(pk=up.pk).exists())

    def test_ue_list_filters_by_query_and_responsable(self):
        ue_a = UE.objects.create(nom="UE Biochimie")
        ue_a.responsables.add(self.teacher)
        UE.objects.create(nom="UE Galénique")
        response = self.client.get(
            reverse("academics:ue_list"),
            {"q": "Bio", "responsable": str(self.teacher.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UE Biochimie")
        self.assertNotContains(response, "UE Galénique")

    def test_up_list_filters_by_ue_and_query(self):
        ue_a = UE.objects.create(nom="UE A")
        ue_b = UE.objects.create(nom="UE B")
        up_a = UP.objects.create(ue=ue_a, nom="UP Analyse", matiere="ANA")
        up_a.responsables.add(self.teacher)
        UP.objects.create(ue=ue_b, nom="UP Galénique", matiere="GAL")
        response = self.client.get(
            reverse("academics:up_list"),
            {"q": "Anal", "ue": str(ue_a.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UP Analyse")
        self.assertNotContains(response, "UP Galénique")
