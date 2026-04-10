from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academics.models import AnneeUniversitaire, Formation, UE, UP
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen
from rooms.models import AffectationSalle, Salle


class SurveillanceRulesTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher2",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )
        self.pool_1 = User.objects.create_user(
            username="pool_1",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        self.pool_2 = User.objects.create_user(
            username="pool_2",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2026/2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation 2")
        self.ue_1 = UE.objects.create(nom="UE Chimie 1")
        self.ue_2 = UE.objects.create(nom="UE Chimie 2")
        self.formation.ues.add(self.ue_1, self.ue_2)
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session 2",
        )
        self.exam_1 = Examen.objects.create(
            session=self.session,
            ue=self.ue_1,
            date=date(2026, 11, 10),
            heure_debut=time(8, 0),
            heure_fin=time(10, 0),
        )
        self.exam_2 = Examen.objects.create(
            session=self.session,
            ue=self.ue_2,
            date=date(2026, 11, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        self.room_1 = Salle.objects.create(nom="Salle 1")
        self.room_2 = Salle.objects.create(nom="Salle 2")
        self.affectation_1 = AffectationSalle.objects.create(
            examen=self.exam_1,
            salle=self.room_1,
            nb_surveillants_requis=2,
        )
        self.affectation_2 = AffectationSalle.objects.create(
            examen=self.exam_2,
            salle=self.room_2,
            nb_surveillants_requis=2,
        )

    def test_quota_blocks_extra_surveillance_for_same_room(self):
        Surveillance.objects.create(affectation_salle=self.affectation_1, surveillant=self.pool_1)
        Surveillance.objects.create(affectation_salle=self.affectation_1, surveillant=self.pool_2)
        third_pool = User.objects.create_user(username="pool_3", password="pass", role=RoleUtilisateur.MEMBRE_POOL)
        surveillance = Surveillance(affectation_salle=self.affectation_1, surveillant=third_pool)
        with self.assertRaises(ValidationError):
            surveillance.full_clean()

    def test_schedule_conflict_blocks_overlapping_surveillance(self):
        Surveillance.objects.create(affectation_salle=self.affectation_1, surveillant=self.pool_1)
        surveillance = Surveillance(affectation_salle=self.affectation_2, surveillant=self.pool_1)
        with self.assertRaises(ValidationError):
            surveillance.full_clean()

    def test_scolarite_user_can_be_assigned_to_surveillance(self):
        scolarite_user = User.objects.create_user(
            username="scolarite_support",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
        )
        surveillance = Surveillance(affectation_salle=self.affectation_1, surveillant=scolarite_user)
        surveillance.full_clean()

    def test_validation_message_is_attached_to_surveillant_field(self):
        Surveillance.objects.create(affectation_salle=self.affectation_1, surveillant=self.pool_1)
        Surveillance.objects.create(affectation_salle=self.affectation_1, surveillant=self.pool_2)
        third_pool = User.objects.create_user(username="pool_4", password="pass", role=RoleUtilisateur.MEMBRE_POOL)
        surveillance = Surveillance(affectation_salle=self.affectation_1, surveillant=third_pool)
        with self.assertRaises(ValidationError) as ctx:
            surveillance.full_clean()
        self.assertIn("surveillant", ctx.exception.message_dict)

    def test_same_user_cannot_be_assigned_to_two_rooms_of_same_exam(self):
        other_room = Salle.objects.create(nom="Salle 3")
        other_affectation = AffectationSalle.objects.create(
            examen=self.exam_1,
            salle=other_room,
            nb_surveillants_requis=1,
        )
        Surveillance.objects.create(affectation_salle=self.affectation_1, surveillant=self.pool_1)
        surveillance = Surveillance(affectation_salle=other_affectation, surveillant=self.pool_1)
        with self.assertRaises(ValidationError) as ctx:
            surveillance.full_clean()
        self.assertIn("surveillant", ctx.exception.message_dict)

    def test_only_one_general_and_one_room_responsable_is_allowed(self):
        Surveillance.objects.create(
            affectation_salle=self.affectation_1,
            surveillant=self.pool_1,
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        surveillance = Surveillance(
            affectation_salle=self.affectation_1,
            surveillant=self.pool_2,
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            surveillance.full_clean()
        self.assertIn("is_responsable_general", ctx.exception.message_dict)
        self.assertIn("is_responsable_salle", ctx.exception.message_dict)

    def test_registration_is_blocked_when_room_is_locked(self):
        current = timezone.localtime()
        dynamic_year = AnneeUniversitaire.objects.create(
            nom="Annee verrouillage",
            date_debut=current.date() - timedelta(days=30),
            date_fin=current.date() + timedelta(days=30),
        )
        dynamic_formation = Formation.objects.create(annee_universitaire=dynamic_year, nom="Formation verrouillage")
        dynamic_ue = UE.objects.create(nom="UE Verrouillage")
        dynamic_formation.ues.add(dynamic_ue)
        dynamic_session = SessionExamen.objects.create(
            formation=dynamic_formation,
            nom="Session verrouillage",
        )
        locked_room = Salle.objects.create(nom="Salle verrouillee")
        locked_exam = Examen.objects.create(
            session=dynamic_session,
            ue=dynamic_ue,
            date=current.date(),
            heure_debut=(current - timedelta(minutes=10)).time().replace(microsecond=0),
            heure_fin=(current + timedelta(minutes=10)).time().replace(microsecond=0),
        )
        locked_affectation = AffectationSalle.objects.create(
            examen=locked_exam,
            salle=locked_room,
            nb_surveillants_requis=1,
        )
        surveillance = Surveillance(affectation_salle=locked_affectation, surveillant=self.pool_1)
        with self.assertRaises(ValidationError) as ctx:
            surveillance.full_clean()
        self.assertIn("affectation_salle", ctx.exception.message_dict)


class SurveillanceCompletionFlowTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_completion",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
            is_staff=True,
        )
        self.pool = User.objects.create_user(
            username="pool_completion",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2027/2028",
            date_debut=date(2027, 9, 1),
            date_fin=date(2028, 7, 31),
            is_active=True,
        )
        formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation completion")
        ue = UE.objects.create(nom="UE Completion")
        formation.ues.add(ue)
        session = SessionExamen.objects.create(
            formation=formation,
            nom="Session completion",
        )
        exam = Examen.objects.create(
            session=session,
            ue=ue,
            nom="Exam Completion",
            date=date(2028, 1, 15),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        salle = Salle.objects.create(nom="Salle Completion")
        self.affectation = AffectationSalle.objects.create(
            examen=exam,
            salle=salle,
            nb_surveillants_requis=2,
        )
        self.client.force_login(self.admin_user)
        session_data = self.client.session
        session_data["active_year_id"] = str(self.year.pk)
        session_data.save()
        self.exam = exam

    def test_delete_surveillance_from_exam_completion(self):
        self.surveillance = Surveillance.objects.create(
            affectation_salle=self.affectation,
            surveillant=self.pool,
        )
        response = self.client.post(
            reverse("exams:exam_surveillance_delete", args=[self.exam.pk, self.surveillance.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inscription supprimée.")
        self.assertFalse(Surveillance.objects.filter(pk=self.surveillance.pk).exists())

    def test_legacy_surveillance_route_is_not_public_anymore(self):
        response = self.client.get("/surveillances/")
        self.assertEqual(response.status_code, 404)

    def test_standard_user_can_self_register_on_a_room(self):
        self.client.force_login(self.pool)
        session_data = self.client.session
        session_data["active_year_id"] = str(self.year.pk)
        session_data.save()
        response = self.client.post(
            reverse("exams:exam_room_register", args=[self.exam.pk, self.affectation.pk]),
            {
                "is_responsable_salle": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inscription à la salle enregistrée.")
        surveillance = Surveillance.objects.get(affectation_salle=self.affectation, surveillant=self.pool)
        self.assertTrue(surveillance.is_responsable_salle)

    def test_standard_user_can_access_completion_page_and_see_signup(self):
        self.client.force_login(self.pool)
        session_data = self.client.session
        session_data["active_year_id"] = str(self.year.pk)
        session_data.save()
        response = self.client.get(reverse("exams:exam_complete", args=[self.exam.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "S'inscrire")
        self.assertContains(response, "Responsable d'épreuve")

    def test_standard_user_sees_responsable_already_defined_messages_when_roles_are_taken(self):
        other_pool = User.objects.create_user(
            username="pool_other_completion",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        Surveillance.objects.create(
            affectation_salle=self.affectation,
            surveillant=other_pool,
            is_responsable_general=True,
            is_responsable_salle=True,
        )
        self.client.force_login(self.pool)
        session_data = self.client.session
        session_data["active_year_id"] = str(self.year.pk)
        session_data.save()
        response = self.client.get(reverse("exams:exam_room_register", args=[self.exam.pk, self.affectation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "responsable déjà défini", count=2)

    def test_standard_user_sees_access_denied_on_admin_room_update_view(self):
        self.client.force_login(self.pool)
        session_data = self.client.session
        session_data["active_year_id"] = str(self.year.pk)
        session_data.save()
        response = self.client.get(reverse("exams:exam_room_update", args=[self.exam.pk, self.affectation.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "veuillez vous referer a un membre du personnel scolarité ou au service informatique", status_code=403)

    def test_admin_can_manually_register_existing_or_new_user(self):
        existing = User.objects.create_user(
            username="existing_pool",
            password="pass",
            email="existing@example.com",
            first_name="Existing",
            last_name="Pool",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        response_existing = self.client.post(
            reverse("exams:exam_room_register", args=[self.exam.pk, self.affectation.pk]),
            {
                "email": "existing@example.com",
            },
            follow=True,
        )
        self.assertEqual(response_existing.status_code, 200)
        self.assertTrue(
            Surveillance.objects.filter(affectation_salle=self.affectation, surveillant=existing).exists()
        )

        scolarite_user = User.objects.create_user(
            username="existing_scolarite",
            password="pass",
            email="scolarite@example.com",
            first_name="Sonia",
            last_name="Admin",
            role=RoleUtilisateur.SCOLARITE,
        )
        response_scolarite = self.client.post(
            reverse("exams:exam_room_register", args=[self.exam.pk, self.affectation.pk]),
            {
                "email": "scolarite@example.com",
            },
            follow=True,
        )
        self.assertEqual(response_scolarite.status_code, 200)
        self.assertTrue(
            Surveillance.objects.filter(affectation_salle=self.affectation, surveillant=scolarite_user).exists()
        )

        other_room = Salle.objects.create(nom="Salle Admin 2")
        other_affectation = AffectationSalle.objects.create(
            examen=self.exam,
            salle=other_room,
            nb_surveillants_requis=2,
        )
        response_new = self.client.post(
            reverse("exams:exam_room_register", args=[self.exam.pk, other_affectation.pk]),
            {
                "email": "new-watcher@example.com",
                "is_responsable_general": "on",
            },
            follow=True,
        )
        self.assertEqual(response_new.status_code, 200)
        self.assertContains(response_new, "Nouvel utilisateur détecté")
        self.assertContains(response_new, "Renseignez le prénom, le nom et le rôle")
        self.assertContains(response_new, 'name="first_name"')
        self.assertContains(response_new, 'name="last_name"')
        self.assertContains(response_new, "UP d'appartenance")
        up = UP.objects.create(nom="Microbiologie")
        response_new_confirmed = self.client.post(
            reverse("exams:exam_room_register", args=[self.exam.pk, other_affectation.pk]),
            {
                "confirm_new_user": "1",
                "first_name": "New",
                "last_name": "Watcher",
                "email": "new-watcher@example.com",
                "is_responsable_general": "True",
                "is_responsable_salle": "",
                "role": RoleUtilisateur.ENSEIGNANT,
                "up": str(up.pk),
            },
            follow=True,
        )
        self.assertEqual(response_new_confirmed.status_code, 200)
        created_user = User.objects.get(email="new-watcher@example.com")
        self.assertEqual(created_user.username, "new.watcher")
        self.assertEqual(created_user.role, RoleUtilisateur.ENSEIGNANT)
        self.assertEqual(created_user.up, up)
        self.assertTrue(created_user.has_usable_password())
        self.assertFalse(created_user.check_password("Pharmexam123!"))
        self.assertContains(response_new_confirmed, "mot de passe temporaire")
        self.assertTrue(
            Surveillance.objects.filter(
                affectation_salle=other_affectation,
                surveillant=created_user,
                is_responsable_general=True,
            ).exists()
        )

    def test_admin_new_teacher_requires_up_selection(self):
        response = self.client.post(
            reverse("exams:exam_room_register", args=[self.exam.pk, self.affectation.pk]),
            {
                "confirm_new_user": "1",
                "first_name": "Anne",
                "last_name": "Teach",
                "email": "anne.teach@example.com",
                "is_responsable_general": "",
                "is_responsable_salle": "",
                "role": RoleUtilisateur.ENSEIGNANT,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sélectionnez l&#x27;UP d&#x27;appartenance pour cet enseignant.")

    def test_admin_registration_form_only_requests_email_before_new_user_step(self):
        response = self.client.get(reverse("exams:exam_room_register", args=[self.exam.pk, self.affectation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')
        self.assertNotContains(response, 'name="first_name"')
        self.assertNotContains(response, 'name="last_name"')

    def test_admin_can_reassign_general_responsable(self):
        second_pool = User.objects.create_user(
            username="pool_second_completion",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        first = Surveillance.objects.create(
            affectation_salle=self.affectation,
            surveillant=self.pool,
        )
        first.is_responsable_general = True
        first.save()
        second = Surveillance.objects.create(
            affectation_salle=self.affectation,
            surveillant=second_pool,
        )
        response = self.client.post(
            reverse("exams:exam_surveillance_responsibility", args=[self.exam.pk, second.pk]),
            {
                "is_responsable_general": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_responsable_general)
        self.assertTrue(second.is_responsable_general)
