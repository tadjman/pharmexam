from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from accounts.models import RoleUtilisateur, User
from exams.models import Examen, SessionExamen

from .models import AnneeUniversitaire, Formation, UE, UP


class AcademicYearPermissionTests(TestCase):
    def setUp(self):
        self.scolarite = User.objects.create_user(username="scolarite_user", password="pass", role=RoleUtilisateur.SCOLARITE)
        self.teacher = User.objects.create_user(username="teacher_user", password="pass", role=RoleUtilisateur.ENSEIGNANT)

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
        self.user = User.objects.create_user(username="middleware_user", password="pass", role=RoleUtilisateur.SCOLARITE)

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
        self.user = User.objects.create_user(username="active_year_user", password="pass", role=RoleUtilisateur.SCOLARITE)
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
        response = self.client.post(reverse("academics:annee_set_active", args=[self.year_two.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.year_one.refresh_from_db()
        self.year_two.refresh_from_db()
        self.assertFalse(self.year_one.is_active)
        self.assertTrue(self.year_two.is_active)
        self.assertEqual(self.client.session.get("active_year_id"), str(self.year_two.pk))
        self.assertContains(response, "Année active définie")

    def test_non_scolarite_user_cannot_set_active_year(self):
        teacher = User.objects.create_user(username="teacher_active_year_denied", password="pass", role=RoleUtilisateur.ENSEIGNANT)
        self.client.force_login(teacher)
        response = self.client.post(reverse("academics:annee_set_active", args=[self.year_two.pk]), follow=True)
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


class AcademicCatalogViewsTests(TestCase):
    def setUp(self):
        self.scolarite = User.objects.create_user(username="scolarite_catalog", password="pass", role=RoleUtilisateur.SCOLARITE)
        self.teacher = User.objects.create_user(username="teacher_catalog", password="pass", role=RoleUtilisateur.ENSEIGNANT)
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

    def test_scolarite_user_can_create_formation(self):
        ue = UE.objects.create(nom="UE Pharmacie")
        response = self.client.post(
            reverse("academics:formation_create"),
            {"nom": "DFGSP2", "ues": [str(ue.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        formation = Formation.objects.get(nom="DFGSP2")
        self.assertEqual(formation.annee_universitaire, self.year)
        self.assertTrue(formation.ues.filter(pk=ue.pk).exists())
        self.assertEqual(
            list(formation.sessions.order_by("date_debut").values_list("nom", flat=True)),
            ["Semestre 1", "Semestre 2", "Rattrapages"],
        )
        self.assertContains(response, "Formation créée.")

    def test_new_formation_gets_default_sessions(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation par defaut")
        self.assertEqual(formation.sessions.count(), 3)
        self.assertSetEqual(
            set(formation.sessions.values_list("nom", flat=True)),
            {"Semestre 1", "Semestre 2", "Rattrapages"},
        )

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
            {"ue": str(ue.pk), "nom": "UP Galénique", "matiere": "GAL", "responsables": [str(self.teacher.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UP.objects.filter(nom="UP Galénique", ue=ue).exists())
        self.assertContains(response, "UP créée.")

    def test_up_delete_is_blocked_when_linked_to_exam(self):
        ue = UE.objects.create(nom="UE Delete")
        ue.responsables.add(self.teacher)
        up = UP.objects.create(ue=ue, nom="UP Delete", matiere="DEL")
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation liée")
        formation.ues.add(ue)
        session = SessionExamen.objects.create(
            formation=formation,
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

    def test_formation_list_displays_active_year_formations_without_filter_block(self):
        ue_a = UE.objects.create(nom="UE Biochimie")
        ue_b = UE.objects.create(nom="UE Galénique")
        formation_a = Formation.objects.create(annee_universitaire=self.year, nom="DFGSP2")
        formation_a.ues.add(ue_a)
        formation_b = Formation.objects.create(annee_universitaire=self.year, nom="DFASP1")
        formation_b.ues.add(ue_b)
        response = self.client.get(reverse("academics:formation_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DFGSP2")
        self.assertContains(response, "DFASP1")
        self.assertContains(response, "Sélectionnez année universitaire")
        self.assertNotContains(response, "Afficher")

    def test_year_list_displays_details_entry_points(self):
        other_year = AnneeUniversitaire.objects.create(
            nom="2026/2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=False,
        )
        Formation.objects.create(annee_universitaire=other_year, nom="Formation historique")
        response = self.client.get(reverse("academics:annee_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Détails")
        self.assertContains(response, "Définir comme active")

    def test_year_detail_lists_its_formations(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="DFGSP3")
        response = self.client.get(reverse("academics:annee_detail", args=[self.year.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DFGSP3")
        self.assertContains(response, "Formations rattachées")

    def test_formation_list_can_switch_year(self):
        other_year = AnneeUniversitaire.objects.create(
            nom="2026/2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=False,
        )
        Formation.objects.create(annee_universitaire=self.year, nom="Formation active")
        Formation.objects.create(annee_universitaire=other_year, nom="Formation historique")
        response = self.client.get(reverse("academics:formation_list"), {"year": str(other_year.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Formation historique")
        self.assertNotContains(response, "Formation active")

    def test_ue_list_displays_catalog_without_filter_block(self):
        ue_a = UE.objects.create(nom="UE Biochimie")
        ue_a.responsables.add(self.teacher)
        UE.objects.create(nom="UE Galénique")
        response = self.client.get(reverse("academics:ue_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UE Biochimie")
        self.assertContains(response, "UE Galénique")
        self.assertNotContains(response, "Recherche")

    def test_up_list_displays_catalog_without_filter_block(self):
        ue_a = UE.objects.create(nom="UE A")
        ue_b = UE.objects.create(nom="UE B")
        up_a = UP.objects.create(ue=ue_a, nom="UP Analyse", matiere="ANA")
        up_a.responsables.add(self.teacher)
        UP.objects.create(ue=ue_b, nom="UP Galénique", matiere="GAL")
        response = self.client.get(reverse("academics:up_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UP Analyse")
        self.assertContains(response, "UP Galénique")
        self.assertNotContains(response, "Filtrer")

    def test_formation_detail_displays_ues_and_responsables(self):
        ue = UE.objects.create(nom="UE Synthèse")
        ue.responsables.add(self.teacher)
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation détail")
        formation.ues.add(ue)
        response = self.client.get(reverse("academics:formation_detail", args=[formation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UE Synthèse")
        self.assertContains(response, self.teacher.username)
