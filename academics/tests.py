from datetime import date, time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import RoleUtilisateur, User
from exams.models import Examen, SessionExamen

from .models import AnneeUniversitaire, Formation, UE, UE_COLOR_PALETTE, UP


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
        up = UP.objects.create(nom="Pharmacologie")
        response = self.client.post(
            reverse("academics:formation_create"),
            {
                "nom": "DEUST",
                "formation_year_label": "2ème année",
                "ues-TOTAL_FORMS": "1",
                "ues-INITIAL_FORMS": "0",
                "ues-MIN_NUM_FORMS": "0",
                "ues-MAX_NUM_FORMS": "1000",
                "ues-0-code_ue": "ue1s25",
                "ues-0-nom": "UE Pharmacie",
                "ues-0-ups": [str(up.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        formation = Formation.objects.get(nom="DEUST (2ème année)")
        self.assertEqual(formation.annee_universitaire, self.year)
        ue = formation.ues.get()
        self.assertEqual(ue.code_ue, "UE1S25")
        self.assertEqual(ue.nom, "UE Pharmacie")
        self.assertTrue(ue.ups.filter(pk=up.pk).exists())
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
                "ues-TOTAL_FORMS": "1",
                "ues-INITIAL_FORMS": "0",
                "ues-MIN_NUM_FORMS": "0",
                "ues-MAX_NUM_FORMS": "1000",
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
        self.assertContains(response, "Nom de l'UE")
        self.assertContains(response, "UP rattachées")
        self.assertNotContains(response, "Responsables")

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
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation UE directe")
        up = UP.objects.create(nom="Anatomie")
        response_ue = self.client.post(
            reverse("academics:ue_create"),
            {
                "formation": str(formation.pk),
                "code_ue": "ue1s25",
                "nom": "UE Biochimie",
                "ups": [str(up.pk)],
            },
            follow=True,
        )
        self.assertEqual(response_ue.status_code, 200)
        self.assertTrue(
            UE.objects.filter(nom="UE Biochimie", code_ue="UE1S25", formation=formation).exists()
        )

    def test_ue_create_page_displays_creation_title(self):
        response = self.client.get(reverse("academics:ue_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvelle UE")
        self.assertNotContains(response, "Modifier l&#x27;UE")
        self.assertNotContains(response, "Responsables")

    def test_ue_update_page_returns_to_formation(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation UE détail")
        ue = UE.objects.create(formation=formation, code_ue="UE7S30", nom="UE Physiologie")
        response = self.client.get(reverse("academics:ue_update", args=[ue.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Retour à la formation")
        self.assertContains(response, reverse("academics:formation_detail", args=[formation.pk]))

    def test_formation_detail_displays_ue_modify_links(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation détails UE")
        ue = UE.objects.create(formation=formation, nom="UE Détail")
        response = self.client.get(reverse("academics:formation_detail", args=[formation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modifier")
        self.assertContains(response, reverse("academics:ue_update", args=[ue.pk]))
        self.assertNotContains(response, ">Détails<", html=False)

    def test_ue_list_displays_modify_links(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation liste UE")
        ue = UE.objects.create(formation=formation, nom="UE Liste")
        response = self.client.get(reverse("academics:ue_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modifier")
        self.assertContains(response, reverse("academics:ue_update", args=[ue.pk]))

    def test_ue_color_is_generated_automatically_from_non_functional_palette(self):
        ue = UE.objects.create(nom="UE Colorée")
        self.assertTrue(ue.code_ue.startswith("UE"))
        self.assertIn(ue.couleur, UE_COLOR_PALETTE)

    def test_ue_color_assignment_uses_palette_randomization(self):
        self.assertEqual(len(UE_COLOR_PALETTE), 12)
        with patch("academics.models.random.choice", return_value=UE_COLOR_PALETTE[3]) as mocked_choice:
            ue = UE.objects.create(nom="UE Palette aléatoire")
        mocked_choice.assert_called_once_with(UE_COLOR_PALETTE)
        self.assertEqual(ue.couleur, UE_COLOR_PALETTE[3])

    def test_ue_color_assignment_avoids_duplicate_colors_while_palette_has_free_colors(self):
        first = UE.objects.create(nom="UE Couleur 1", couleur=UE_COLOR_PALETTE[0])
        self.assertEqual(first.couleur, UE_COLOR_PALETTE[0])
        expected_choices = tuple(UE_COLOR_PALETTE[1:])
        with patch("academics.models.random.choice", return_value=UE_COLOR_PALETTE[1]) as mocked_choice:
            ue = UE.objects.create(nom="UE Couleur 2")
        mocked_choice.assert_called_once_with(expected_choices)
        self.assertEqual(ue.couleur, UE_COLOR_PALETTE[1])

    def test_ue_color_assignment_allows_reuse_only_when_all_colors_are_already_used(self):
        for index, color in enumerate(UE_COLOR_PALETTE):
            UE.objects.create(nom=f"UE Couleur pleine {index}", couleur=color)
        with patch("academics.models.random.choice", return_value=UE_COLOR_PALETTE[0]) as mocked_choice:
            ue = UE.objects.create(nom="UE Couleur 13")
        mocked_choice.assert_called_once_with(UE_COLOR_PALETTE)
        self.assertEqual(ue.couleur, UE_COLOR_PALETTE[0])

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

    def test_formation_detail_displays_ues_and_ups(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation détail")
        ue = UE.objects.create(nom="UE Synthèse", formation=formation)
        up = UP.objects.create(nom="Biologie cellulaire")
        ue.ups.add(up)
        response = self.client.get(reverse("academics:formation_detail", args=[formation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UE Synthèse")
        self.assertContains(response, "1 UP")
        self.assertContains(response, ue.couleur)
        self.assertNotContains(response, up.nom)
        self.assertNotContains(response, "Responsables")

    def test_up_list_displays_up_section(self):
        UP.objects.create(nom="Physiologie")
        response = self.client.get(reverse("academics:up_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unités pédagogiques")
        self.assertContains(response, "Physiologie")
        self.assertContains(response, "Voir les formations")
        self.assertContains(response, "+ Nouvelle UP")
        self.assertContains(response, "Détails")
        self.assertNotContains(response, 'name="nom"')

    def test_default_internal_up_is_hidden_from_up_list(self):
        UP.get_default_up()
        visible_up = UP.objects.create(nom="Physiologie")
        response = self.client.get(reverse("academics:up_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, visible_up.nom)
        self.assertNotContains(response, "Autre")

    def test_up_create_page_displays_creation_title(self):
        response = self.client.get(reverse("academics:up_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvelle UP")
        self.assertContains(response, "Retour")
        self.assertContains(response, 'name="nom"')

    def test_default_internal_up_is_hidden_from_up_detail_and_update(self):
        default_up = UP.get_default_up()
        detail_response = self.client.get(reverse("academics:up_detail", args=[default_up.pk]))
        update_response = self.client.get(reverse("academics:up_update", args=[default_up.pk]))
        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(update_response.status_code, 404)

    def test_up_detail_displays_attached_users_and_modify_button(self):
        up = UP.objects.create(nom="Physiologie")
        teacher = User.objects.create_user(
            username="teacher.up.detail",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            first_name="lea",
            last_name="martin",
            email="LEA.MARTIN@EXAMPLE.COM",
            up=up,
        )
        response = self.client.get(reverse("academics:up_detail", args=[up.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Utilisateurs rattachés")
        self.assertContains(response, "Lea MARTIN")
        self.assertContains(response, "Enseignant")
        self.assertContains(response, "lea.martin@example.com")
        self.assertContains(response, "Retour")
        self.assertContains(response, "Modifier")
        self.assertContains(response, reverse("academics:up_update", args=[up.pk]))

    def test_up_update_page_displays_delete_button(self):
        up = UP.objects.create(nom="Immunologie")
        response = self.client.get(reverse("academics:up_update", args=[up.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modifier l'UP")
        self.assertContains(response, "Supprimer")
        self.assertContains(response, "Êtes-vous sûr de vouloir supprimer cette UP ?")

    def test_scolarite_can_create_and_delete_up(self):
        create_response = self.client.post(
            reverse("academics:up_create"),
            {"nom": "Immunologie"},
            follow=True,
        )
        self.assertEqual(create_response.status_code, 200)
        up = UP.objects.get(nom="Immunologie")
        self.assertContains(create_response, "UP créée.")

        delete_response = self.client.post(
            reverse("academics:up_delete", args=[up.pk]),
            follow=True,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertContains(delete_response, "UP supprimée.")
        self.assertFalse(UP.objects.filter(pk=up.pk).exists())

    def test_formation_update_route_is_removed(self):
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation sans modification")
        response = self.client.get(f"/formations/{formation.pk}/modifier/")
        self.assertEqual(response.status_code, 404)

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
