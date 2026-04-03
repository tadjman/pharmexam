from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from accounts.models import RoleUtilisateur, User
from exams.models import Examen, SessionExamen

from .models import AnneeUniversitaire, Formation, UE, UE_COLOR_PALETTE


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
        self.assertContains(response, "veuillez vous referer a un membre du personnel scolarité ou au service informatique", status_code=403)

    def test_scolarite_user_can_access_year_creation(self):
        self.client.force_login(self.scolarite)
        response = self.client.get(reverse("academics:annee_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvelle année universitaire")
        self.assertNotContains(response, 'name="nom"')

    def test_non_scolarite_user_cannot_access_year_list(self):
        year = AnneeUniversitaire.objects.create(
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=True,
        )
        self.client.force_login(self.teacher)
        session = self.client.session
        session["active_year_id"] = str(year.pk)
        session.save()
        response = self.client.get(reverse("academics:annee_list"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "veuillez vous referer a un membre du personnel scolarité ou au service informatique", status_code=403)


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
        self.assertEqual(response.status_code, 403)
        self.year_one.refresh_from_db()
        self.year_two.refresh_from_db()
        self.assertTrue(self.year_one.is_active)
        self.assertFalse(self.year_two.is_active)
        self.assertContains(response, "veuillez vous referer a un membre du personnel scolarité ou au service informatique", status_code=403)

    def test_saving_active_year_deactivates_previous_one(self):
        self.year_two.is_active = True
        self.year_two.save()
        self.year_one.refresh_from_db()
        self.year_two.refresh_from_db()
        self.assertFalse(self.year_one.is_active)
        self.assertTrue(self.year_two.is_active)

    def test_year_name_is_generated_from_dates(self):
        generated_year = AnneeUniversitaire.objects.create(
            date_debut=date(2028, 9, 1),
            date_fin=date(2029, 7, 31),
            is_active=False,
        )
        self.assertEqual(generated_year.nom, "2028/2029")

    def test_year_name_gets_suffix_when_base_label_already_exists(self):
        first = AnneeUniversitaire.objects.create(
            date_debut=date(2030, 9, 1),
            date_fin=date(2031, 7, 31),
            is_active=False,
        )
        second = AnneeUniversitaire.objects.create(
            date_debut=date(2030, 10, 1),
            date_fin=date(2031, 6, 30),
            is_active=False,
        )
        self.assertEqual(first.nom, "2030/2031")
        self.assertEqual(second.nom, "2030/2031 [2]")


class AcademicCatalogViewsTests(TestCase):
    def setUp(self):
        self.scolarite = User.objects.create_user(
            username="scolarite_catalog",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
        )
        self.teacher = User.objects.create_user(
            username="teacher_catalog",
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

    def test_scolarite_user_can_create_formation_and_default_sessions(self):
        ue = UE.objects.create(nom="UE Pharmacie")
        response = self.client.post(
            reverse("academics:formation_create"),
            {
                "nom": "DEUST",
                "formation_year_label": "2ème année",
                "ues": [str(ue.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        formation = Formation.objects.get(nom="DEUST (2ème année)")
        self.assertEqual(formation.annee_universitaire, self.year)
        self.assertTrue(formation.ues.filter(pk=ue.pk).exists())
        self.assertSetEqual(
            set(formation.sessions.values_list("nom", flat=True)),
            {"Semestre 1", "Semestre 2", "Rattrapages"},
        )
        self.assertContains(response, "Formation créée.")

    def test_unique_year_label_does_not_append_suffix_to_formation_name(self):
        response = self.client.post(
            reverse("academics:formation_create"),
            {
                "nom": "Formation Continue",
                "formation_year_label": "Année unique",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Formation.objects.filter(nom="Formation Continue").exists())
        self.assertFalse(Formation.objects.filter(nom="Formation Continue (Année unique)").exists())

    def test_formation_create_page_displays_year_label_selector(self):
        response = self.client.get(reverse("academics:formation_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Année ?")
        self.assertContains(response, "Année unique")
        self.assertContains(response, "2ème année")

    def test_scolarite_user_can_create_year_without_manual_name(self):
        response = self.client.post(
            reverse("academics:annee_create"),
            {
                "date_debut": "2031-09-01",
                "date_fin": "2032-07-31",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AnneeUniversitaire.objects.filter(
                nom="2031/2032",
                date_debut=date(2031, 9, 1),
                date_fin=date(2032, 7, 31),
            ).exists()
        )
        self.assertContains(response, "Année universitaire créée.")

    def test_year_create_page_displays_creation_title(self):
        response = self.client.get(reverse("academics:annee_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvelle année universitaire")
        self.assertNotContains(response, "Modifier l'année universitaire")

    def test_scolarite_user_can_create_ue(self):
        response_ue = self.client.post(
            reverse("academics:ue_create"),
            {"code_ue": "ue1s25", "nom": "UE Biochimie", "responsables": [str(self.teacher.pk)]},
            follow=True,
        )
        self.assertEqual(response_ue.status_code, 200)
        self.assertTrue(UE.objects.filter(nom="UE Biochimie", code_ue="UE1S25").exists())

    def test_ue_create_page_displays_creation_title(self):
        response = self.client.get(reverse("academics:ue_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvelle UE")
        self.assertNotContains(response, "Modifier l&#x27;UE")

    def test_ue_color_is_generated_automatically_from_non_functional_palette(self):
        ue = UE.objects.create(nom="UE Colorée")
        self.assertTrue(ue.code_ue.startswith("UE"))
        self.assertIn(ue.couleur, UE_COLOR_PALETTE)

    def test_ue_colors_follow_fixed_palette_without_random_generation(self):
        self.assertEqual(len(UE_COLOR_PALETTE), 16)
        created = [UE.objects.create(nom=f"UE Palette {index}") for index in range(17)]
        first_sixteen_colors = [ue.couleur for ue in created[:16]]
        self.assertEqual(first_sixteen_colors, list(UE_COLOR_PALETTE))
        self.assertEqual(created[16].couleur, UE_COLOR_PALETTE[0])

    def test_ue_delete_is_blocked_when_linked_to_exam(self):
        ue = UE.objects.create(nom="UE Delete")
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation liée")
        formation.ues.add(ue)
        session = SessionExamen.objects.create(
            formation=formation,
            nom="Session liée",
        )
        Examen.objects.create(
            session=session,
            ue=ue,
            nom="Exam lié",
            date=date(2028, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        response = self.client.post(reverse("academics:ue_delete", args=[ue.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible")
        self.assertTrue(UE.objects.filter(pk=ue.pk).exists())

    def test_formation_list_uses_active_year_formations(self):
        Formation.objects.create(annee_universitaire=self.year, nom="DFGSP2")
        other_year = AnneeUniversitaire.objects.create(
            nom="2026/2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=False,
        )
        Formation.objects.create(annee_universitaire=other_year, nom="Formation historique")
        response = self.client.get(reverse("academics:formation_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DFGSP2")
        self.assertNotContains(response, "Formation historique")

    def test_formation_list_displays_active_year_context(self):
        other_year = AnneeUniversitaire.objects.create(
            nom="2026/2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=False,
        )
        Formation.objects.create(annee_universitaire=other_year, nom="Formation inactive")
        response = self.client.get(reverse("academics:formation_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Année active")
        self.assertContains(response, self.year.nom)
        self.assertNotContains(response, "Attention, année inactive")

    def test_year_list_and_detail_display_formations(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="DFGSP3")
        list_response = self.client.get(reverse("academics:annee_list"))
        detail_response = self.client.get(reverse("academics:annee_detail", args=[self.year.pk]))
        self.assertContains(list_response, "Détails")
        self.assertContains(detail_response, formation.nom)
        self.assertContains(detail_response, "Formations rattachées")

    def test_formation_detail_displays_ues_and_responsables(self):
        ue = UE.objects.create(nom="UE Synthèse")
        self.teacher.first_name = "aLi"
        self.teacher.last_name = "taDjine"
        self.teacher.save()
        ue.responsables.add(self.teacher)
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation détail")
        formation.ues.add(ue)
        response = self.client.get(reverse("academics:formation_detail", args=[formation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UE Synthèse")
        self.assertContains(response, "Ali TADJINE")

    def test_formation_update_displays_delete_button_when_sessions_have_no_exams(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation supprimable")
        response = self.client.get(reverse("academics:formation_update", args=[formation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Supprimer")
        self.assertContains(response, "Êtes-vous sûr de vouloir supprimer cette formation ?")

    def test_formation_update_hides_delete_button_when_sessions_have_exams(self):
        ue = UE.objects.create(nom="UE Formation bloquée")
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation bloquée")
        formation.ues.add(ue)
        session = formation.sessions.first()
        Examen.objects.create(
            session=session,
            ue=ue,
            nom="Examen formation bloquée",
            date=date(2028, 2, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        response = self.client.get(reverse("academics:formation_update", args=[formation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Êtes-vous sûr de vouloir supprimer cette formation ?")
        self.assertContains(response, "Suppression indisponible")

    def test_formation_delete_removes_empty_sessions_and_formation(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation à supprimer")
        session_ids = list(formation.sessions.values_list("pk", flat=True))
        response = self.client.post(reverse("academics:formation_delete", args=[formation.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Formation supprimée.")
        self.assertFalse(Formation.objects.filter(pk=formation.pk).exists())
        self.assertFalse(SessionExamen.objects.filter(pk__in=session_ids).exists())

    def test_formation_delete_is_blocked_when_sessions_have_exams(self):
        ue = UE.objects.create(nom="UE Delete formation blocked")
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation non supprimable")
        formation.ues.add(ue)
        session = formation.sessions.first()
        Examen.objects.create(
            session=session,
            ue=ue,
            nom="Examen bloquant suppression formation",
            date=date(2028, 3, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        response = self.client.post(reverse("academics:formation_delete", args=[formation.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible : cette formation contient encore des examens dans ses sessions.")
        self.assertTrue(Formation.objects.filter(pk=formation.pk).exists())

    def test_nav_hides_year_link_for_non_scolarite_user(self):
        self.client.force_login(self.teacher)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()
        response = self.client.get(reverse("academics:formation_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Années universitaires")
