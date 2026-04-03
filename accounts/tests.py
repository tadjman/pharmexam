from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from academics.models import AnneeUniversitaire, Formation, UE
from accounts.models import RoleUtilisateur, User
from exams.models import Examen, SessionExamen
from rooms.models import AffectationSalle, Salle


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="adam",
            password="pass123",
            role=RoleUtilisateur.SCOLARITE,
        )

    def test_dashboard_redirects_anonymous_user_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connexion")
        self.assertContains(response, "Nom d’utilisateur")

    def test_valid_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": "adam", "password": "pass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_user_is_admin_helper_reflects_staff_flag(self):
        self.assertFalse(self.user.is_admin())
        self.user.is_staff = True
        self.assertTrue(self.user.is_admin())

    def test_user_display_helpers_normalize_name_and_email(self):
        user = User.objects.create_user(
            username="format_test",
            password="pass123",
            role=RoleUtilisateur.MEMBRE_POOL,
            first_name="aDaM",
            last_name="taDjiNe",
            email="ADAM.TADJINE@EXAMPLE.COM",
        )
        self.assertEqual(user.display_first_name, "Adam")
        self.assertEqual(user.display_last_name, "TADJINE")
        self.assertEqual(user.display_full_name, "Adam TADJINE")
        self.assertEqual(user.display_email, "adam.tadjine@example.com")

    def test_dashboard_displays_kpis_when_active_year_exists(self):
        year = AnneeUniversitaire.objects.create(
            nom="2033/2034",
            date_debut="2033-09-01",
            date_fin="2034-07-31",
            is_active=True,
        )
        formation = Formation.objects.create(
            annee_universitaire=year,
            nom="Formation KPI",
        )
        ue = UE.objects.create(nom="UE KPI")
        formation.ues.add(ue)
        session = SessionExamen.objects.create(
            formation=formation,
            nom="Session KPI",
        )
        exam = Examen.objects.create(
            session=session,
            ue=ue,
            nom="Exam KPI",
            date=date(2034, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        salle = Salle.objects.create(nom="Salle KPI")
        AffectationSalle.objects.create(
            examen=exam,
            salle=salle,
            nb_surveillants_requis=2,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Tableau de bord {year.nom}")
        self.assertContains(response, "surveillants manquants")
        self.assertContains(response, "Formations avec examens incomplets")
        self.assertContains(response, "Examens à compléter")
        self.assertContains(response, "Formation KPI")
        self.assertContains(response, "Exam KPI")

    def test_navbar_exposes_main_sections_and_no_admin_for_non_staff(self):
        year = AnneeUniversitaire.objects.create(
            nom="2034/2035",
            date_debut="2034-09-01",
            date_fin="2035-07-31",
            is_active=True,
        )
        Formation.objects.create(annee_universitaire=year, nom="Formation Navbar")
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        nav_html = response.content.decode().split('<nav class="nav">', 1)[1].split("</nav>", 1)[0]
        self.assertIn("Tableau de bord", nav_html)
        self.assertIn("Années universitaires", nav_html)
        self.assertIn("Formations", nav_html)
        self.assertIn("Examens", nav_html)
        self.assertIn("Suivi", nav_html)
        self.assertNotIn("Exports", nav_html)
        self.assertNotIn("Admin", nav_html)

    def test_admin_index_uses_pharmexam_branding(self):
        admin_user = User.objects.create_superuser(
            username="admin_branding",
            password="pass123",
            email="admin@example.com",
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administration Pharmexam")
        self.assertContains(response, "Retour à l'application")
