from django.test import TestCase
from django.urls import reverse

from academics.models import AnneeUniversitaire, UE, UP
from accounts.models import RoleUtilisateur, User
from exams.models import Examen, SessionExamen


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

    def test_dashboard_displays_kpis_when_active_year_exists(self):
        teacher = User.objects.create_user(
            username="teacher_dashboard",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )
        year = AnneeUniversitaire.objects.create(
            nom="2033/2034",
            date_debut="2033-09-01",
            date_fin="2034-07-31",
            is_active=True,
        )
        session = SessionExamen.objects.create(
            annee_universitaire=year,
            nom="Session KPI",
            date_debut="2034-01-01",
            date_fin="2034-01-31",
        )
        ue = UE.objects.create(nom="UE KPI")
        ue.responsables.add(teacher)
        up = UP.objects.create(ue=ue, nom="UP KPI", matiere="KPI")
        Examen.objects.create(
            session=session,
            up=up,
            nom="Exam KPI",
            date="2034-01-10",
            heure_debut="09:00",
            heure_fin="11:00",
            nb_eleves=20,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=teacher,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Taux de complétion")
        self.assertContains(response, "Exam KPI")
