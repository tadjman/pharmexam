from datetime import date, time

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from academics.models import AnneeUniversitaire, Formation, UE, UP
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
        self.assertContains(response, "S'inscrire")
        self.assertContains(response, '/media/favicon.png')

    def test_signup_page_renders(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inscription")
        self.assertContains(response, "Nom")
        self.assertContains(response, "Prénom")
        self.assertContains(response, "Adresse mail")
        self.assertContains(response, "Mot de passe")

    def test_valid_signup_creates_member_pool_user_and_logs_in(self):
        year = AnneeUniversitaire.objects.create(
            nom="2038/2039",
            date_debut="2038-09-01",
            date_fin="2039-07-31",
            is_active=True,
        )
        response = self.client.post(
            reverse("signup"),
            {
                "last_name": "Dupont",
                "first_name": "Alice",
                "email": "ALICE.DUPONT@EXAMPLE.COM",
                "password1": "MotDePasseTresSolide123!",
                "password2": "MotDePasseTresSolide123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created_user = User.objects.get(email="alice.dupont@example.com")
        self.assertEqual(created_user.username, "alice.dupont")
        self.assertEqual(created_user.role, RoleUtilisateur.MEMBRE_POOL)
        self.assertEqual(created_user.up.nom, "Autre")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(created_user.pk))
        self.assertContains(response, "Compte créé.")
        self.assertContains(response, f"Tableau de bord {year.nom}")

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

    def test_user_save_normalizes_username_to_first_dot_last_for_new_users(self):
        user = User.objects.create_user(
            username="placeholder",
            password="pass123",
            role=RoleUtilisateur.MEMBRE_POOL,
            first_name="Ada",
            last_name="Lovelace",
        )
        self.assertEqual(user.username, "ada.lovelace")

    def test_user_save_normalizes_blank_email_to_none(self):
        user = User.objects.create_user(
            username="email.none",
            password="pass123",
            role=RoleUtilisateur.MEMBRE_POOL,
            email="   ",
        )
        self.assertIsNone(user.email)

    def test_user_gets_default_up_when_none_is_provided(self):
        user = User.objects.create_user(
            username="user.default.up",
            password="pass123",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        self.assertIsNotNone(user.up)
        self.assertEqual(user.up.nom, "Autre")

    def test_user_email_is_unique_when_provided(self):
        User.objects.create_user(
            username="first.email",
            password="pass123",
            role=RoleUtilisateur.MEMBRE_POOL,
            email="duplicate@example.com",
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="second.email",
                password="pass123",
                role=RoleUtilisateur.MEMBRE_POOL,
                email="duplicate@example.com",
            )

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
        ue = UE.objects.create(nom="Exam KPI")
        formation.ues.add(ue)
        session = SessionExamen.objects.create(
            formation=formation,
            nom="Session KPI",
        )
        exam = Examen.objects.create(
            session=session,
            ue=ue,
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
        self.assertContains(response, "Gérer les années")
        self.assertContains(response, "surveillants manquants")
        self.assertContains(response, "Formations avec examens incomplets")
        self.assertNotContains(response, "Examens à compléter")
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
        self.assertNotIn("Années universitaires", nav_html)
        self.assertIn("Enseignement", nav_html)
        self.assertIn("Surveillance", nav_html)
        self.assertIn("Suivi", nav_html)
        self.assertNotIn("Exports", nav_html)
        self.assertNotIn("Admin", nav_html)

    def test_navbar_displays_connected_user_identity_with_role_and_up_for_teacher(self):
        year = AnneeUniversitaire.objects.create(
            nom="2035/2036",
            date_debut="2035-09-01",
            date_fin="2036-07-31",
            is_active=True,
        )
        up = UP.objects.create(nom="Biochimie")
        teacher = User.objects.create_user(
            username="teacher.identity",
            password="pass123",
            role=RoleUtilisateur.ENSEIGNANT,
            first_name="lea",
            last_name="martin",
            up=up,
        )
        self.client.force_login(teacher)
        session = self.client.session
        session["active_year_id"] = str(year.pk)
        session.save()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connecté en tant que")
        self.assertContains(response, "Lea MARTIN · Enseignant · Biochimie")
        self.assertContains(response, "brand__user--teacher")

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
        self.assertContains(response, "Retour")
