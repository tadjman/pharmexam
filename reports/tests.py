from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from academics.models import AnneeUniversitaire, Formation, UE
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen
from rooms.models import AffectationSalle, Salle


class ReportsViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_reports",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
            is_staff=True,
        )
        self.teacher = User.objects.create_user(
            username="teacher_reports",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
            first_name="aDa",
            last_name="loveLace",
            email="ADA.LOVELACE@EXAMPLE.COM",
        )
        self.pool = User.objects.create_user(
            username="pool_reports",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
            first_name="gRace",
            last_name="hopPer",
            email="GRACE.HOPPER@EXAMPLE.COM",
        )
        self.idle_user = User.objects.create_user(
            username="idle_reports",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
            first_name="zero",
            last_name="watcher",
            email="ZERO.WATCHER@EXAMPLE.COM",
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2027/2028",
            date_debut=date(2027, 9, 1),
            date_fin=date(2028, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="DFGSP2")
        self.ue = UE.objects.create(nom="Exam Export")
        self.formation.ues.add(self.ue)
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session export",
        )
        exam = Examen.objects.create(
            session=self.session,
            ue=self.ue,
            date=date(2028, 1, 12),
            heure_debut=time(9, 0),
            heure_fin=time(11, 30),
        )
        room = Salle.objects.create(
            nom="Salle Export",
            capacite=120,
            heure_debut_verrouillage=time(8, 30),
            heure_fin_verrouillage=time(12, 0),
        )
        affectation = AffectationSalle.objects.create(
            examen=exam,
            salle=room,
            temps_majore=True,
            nb_surveillants_requis=2,
        )
        Surveillance.objects.create(affectation_salle=affectation, surveillant=self.teacher)
        Surveillance.objects.create(affectation_salle=affectation, surveillant=self.pool)

        self.client.force_login(self.admin_user)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_activity_report_view_displays_counts_hours_and_room_details(self):
        response = self.client.get(reverse("reports:activity_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suivi des surveillances")
        self.assertContains(response, "Ada LOVELACE")
        self.assertContains(response, "Grace HOPPER")
        self.assertNotContains(response, "Zero WATCHER")
        self.assertContains(response, "badge--role-teacher")
        self.assertContains(response, "badge--role-pool")
        self.assertContains(response, "report-entity-row--teacher")
        self.assertContains(response, "report-entity-row--pool")
        self.assertContains(response, "Enseignant")
        self.assertContains(response, "Membre du pool")
        self.assertContains(response, "ada.lovelace@example.com")
        self.assertContains(response, "grace.hopper@example.com")
        self.assertContains(response, "2h30")
        self.assertContains(response, "Exam Export")
        self.assertContains(response, "Salle Export")
        self.assertContains(response, "DFGSP2")
        self.assertContains(response, "Session export")
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="roles"')
        self.assertContains(response, 'aria-label="Entrée"')
        self.assertContains(response, 'aria-label="Reset"')
        self.assertNotContains(response, "Examens surveillés")
        self.assertNotContains(response, "Heures totales")

    def test_activity_report_orders_users_by_total_hours_descending(self):
        second_ue = UE.objects.create(nom="Exam Export 2")
        self.formation.ues.add(second_ue)
        exam = Examen.objects.create(
            session=self.session,
            ue=second_ue,
            date=date(2028, 1, 13),
            heure_debut=time(14, 0),
            heure_fin=time(17, 0),
        )
        room = Salle.objects.create(nom="Salle Export 2")
        affectation = AffectationSalle.objects.create(
            examen=exam,
            salle=room,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(affectation_salle=affectation, surveillant=self.teacher)

        response = self.client.get(reverse("reports:activity_report"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertLess(content.index("Ada LOVELACE"), content.index("Grace HOPPER"))

    def test_activity_report_filters_by_first_or_last_name_case_insensitive(self):
        response = self.client.get(reverse("reports:activity_report"), {"q": "lovE"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada LOVELACE")
        self.assertNotContains(response, "Grace HOPPER")

    def test_activity_report_filters_by_selected_roles(self):
        response = self.client.get(
            reverse("reports:activity_report"),
            {"filters": "1", "roles": [RoleUtilisateur.ENSEIGNANT]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada LOVELACE")
        self.assertNotContains(response, "Grace HOPPER")

    def test_teacher_only_sees_own_follow_up_and_no_global_export_actions(self):
        self.client.force_login(self.teacher)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

        response = self.client.get(reverse("reports:activity_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada LOVELACE")
        self.assertNotContains(response, "Grace HOPPER")
        self.assertNotContains(response, "Zero WATCHER")
        self.assertNotContains(response, "Centre d'exports")
        self.assertNotContains(response, "Exporter l'année")
        self.assertNotContains(response, 'name="q"')
        self.assertNotContains(response, 'name="roles"')

    def test_pool_member_only_sees_own_follow_up(self):
        self.client.force_login(self.pool)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

        response = self.client.get(reverse("reports:activity_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Grace HOPPER")
        self.assertNotContains(response, "Ada LOVELACE")
        self.assertNotContains(response, "Zero WATCHER")

    def test_teacher_cannot_access_global_exports(self):
        self.client.force_login(self.teacher)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

        export_center_response = self.client.get(reverse("reports:export_center"))
        self.assertEqual(export_center_response.status_code, 403)
        self.assertContains(
            export_center_response,
            "veuillez vous referer a un membre du personnel scolarité ou au service informatique",
            status_code=403,
        )

        export_year_response = self.client.get(reverse("reports:export_year"))
        self.assertEqual(export_year_response.status_code, 403)
        self.assertContains(
            export_year_response,
            "veuillez vous referer a un membre du personnel scolarité ou au service informatique",
            status_code=403,
        )

    def test_year_export_returns_excel_payload(self):
        response = self.client.get(reverse("reports:export_year"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.ms-excel")
        self.assertIn("attachment;", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("Ada LOVELACE", content)
        self.assertIn("Grace HOPPER", content)
        self.assertIn("ada.lovelace@example.com", content)
        self.assertIn("Suivi annee", content)
        self.assertIn("Exam Export", content)
        self.assertIn("Salle Export", content)
        self.assertIn("Detail examens", content)
        self.assertIn("Synthese", content)

    def test_session_export_filters_to_selected_session(self):
        response = self.client.get(reverse("reports:export_session", args=[self.session.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Session export", content)
        self.assertIn("Ada LOVELACE", content)
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
        self.assertIn("120", content)
        self.assertIn("Ada LOVELACE", content)
        self.assertIn("Temps majoré", content)

    def test_exam_session_export_is_scoped_to_selected_session(self):
        response = self.client.get(reverse("reports:export_exam_session", args=[self.session.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Session export", content)
        self.assertIn("Exam Export", content)
        self.assertIn("Salle Export", content)
        self.assertIn("DFGSP2", content)
