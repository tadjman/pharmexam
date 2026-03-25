from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from academics.models import AnneeUniversitaire, Formation, UE, UP
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen
from rooms.models import AffectationSalle, Salle


class ReportsViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_reports", password="pass", role=RoleUtilisateur.SCOLARITE, is_staff=True)
        self.teacher = User.objects.create_user(
            username="teacher_reports",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            first_name="Ada",
            last_name="Lovelace",
        )
        self.pool = User.objects.create_user(
            username="pool_reports",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
            first_name="Grace",
            last_name="Hopper",
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2027/2028",
            date_debut=date(2027, 9, 1),
            date_fin=date(2028, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="DFGSP2")
        ue = UE.objects.create(nom="UE Bio")
        ue.responsables.add(self.teacher)
        self.formation.ues.add(ue)
        up = UP.objects.create(ue=ue, nom="UP Physio", matiere="PH")
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session export",
            date_debut=date(2028, 1, 10),
            date_fin=date(2028, 1, 20),
        )
        exam = Examen.objects.create(
            session=self.session,
            up=up,
            nom="Exam Export",
            date=date(2028, 1, 12),
            heure_debut=time(9, 0),
            heure_fin=time(11, 30),
            nb_eleves=25,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=2,
            responsable=self.teacher,
        )
        room = Salle.objects.create(nom="Salle Export", capacite_max=40)
        AffectationSalle.objects.create(examen=exam, salle=room, is_tiers_temps=False, capacite_reservee=25)
        Surveillance.objects.create(examen=exam, surveillant=self.teacher)
        Surveillance.objects.create(examen=exam, surveillant=self.pool)

        self.client.force_login(self.admin_user)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_activity_report_view_displays_counts_hours_without_filter_block(self):
        response = self.client.get(reverse("reports:activity_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suivi des surveillances")
        self.assertContains(response, "teacher_reports")
        self.assertContains(response, "pool_reports")
        self.assertContains(response, "2h30")
        self.assertContains(response, "Exam Export")
        self.assertContains(response, "DFGSP2")
        self.assertContains(response, "Session export")
        self.assertNotContains(response, "Filtrer")

    def test_year_export_returns_excel_payload(self):
        response = self.client.get(reverse("reports:export_year"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.ms-excel")
        self.assertIn("attachment;", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("teacher_reports", content)
        self.assertIn("pool_reports", content)
        self.assertIn("Suivi annee", content)
        self.assertIn("Exam Export", content)
        self.assertIn("DFGSP2", content)
        self.assertIn("Detail examens", content)
        self.assertIn("Synthese", content)

    def test_session_export_filters_to_selected_session(self):
        response = self.client.get(reverse("reports:export_session", args=[self.session.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Session export", content)
        self.assertIn("teacher_reports", content)
        self.assertIn("DFGSP2", content)

    def test_export_center_view_lists_available_exports(self):
        response = self.client.get(reverse("reports:export_center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Export métier examens")
        self.assertContains(response, "Exports par formation et session")
        self.assertContains(response, "DFGSP2")

    def test_exam_year_export_contains_exam_room_and_surveillance_sheets(self):
        response = self.client.get(reverse("reports:export_exam_year"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Examens", content)
        self.assertIn("Salles", content)
        self.assertIn("Surveillances", content)
        self.assertIn("Exam Export", content)
        self.assertIn("Salle Export", content)
        self.assertIn("teacher_reports", content)
        self.assertIn("DFGSP2", content)

    def test_exam_session_export_is_scoped_to_selected_session(self):
        response = self.client.get(reverse("reports:export_exam_session", args=[self.session.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Session export", content)
        self.assertIn("Exam Export", content)
        self.assertIn("Salle Export", content)
        self.assertIn("DFGSP2", content)
