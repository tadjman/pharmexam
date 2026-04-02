from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academics.models import AnneeUniversitaire, Formation, UE
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen, StatutExamen
from rooms.models import AffectationSalle, Salle


class RoomDeleteViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_room_delete",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
            is_staff=True,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2029/2030",
            date_debut=date(2029, 9, 1),
            date_fin=date(2030, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation room delete")
        self.ue = UE.objects.create(nom="UE Room Delete")
        self.formation.ues.add(self.ue)
        self.session = SessionExamen.objects.create(
            formation=self.formation,
            nom="Session room delete",
        )
        self.exam = Examen.objects.create(
            session=self.session,
            ue=self.ue,
            nom="Exam room delete",
            date=date(2030, 1, 15),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
        )
        self.salle = Salle.objects.create(nom="B201")
        self.affectation = AffectationSalle.objects.create(
            examen=self.exam,
            salle=self.salle,
            nb_surveillants_requis=1,
        )

        self.client.force_login(self.admin_user)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_delete_protected_salle_returns_message_instead_of_500(self):
        response = self.client.post(reverse("rooms:salle_delete", args=[self.salle.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible")
        self.assertTrue(Salle.objects.filter(pk=self.salle.pk).exists())

    def test_delete_affectation_from_exam_completion_is_now_allowed(self):
        response = self.client.post(
            reverse("exams:exam_room_delete", args=[self.exam.pk, self.affectation.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Salle supprimée pour cet examen.")
        self.assertFalse(AffectationSalle.objects.filter(pk=self.affectation.pk).exists())
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.statut, StatutExamen.INITIE)

    def test_delete_affectation_is_blocked_when_watchers_are_still_registered(self):
        watcher = User.objects.create_user(
            username="watcher_room_delete",
            password="pass",
            role=RoleUtilisateur.MEMBRE_POOL,
        )
        Surveillance.objects.create(affectation_salle=self.affectation, surveillant=watcher)
        response = self.client.post(
            reverse("exams:exam_room_delete", args=[self.exam.pk, self.affectation.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible")
        self.assertTrue(AffectationSalle.objects.filter(pk=self.affectation.pk).exists())

    def test_room_list_displays_available_rooms_without_capacity_wording(self):
        Salle.objects.create(nom="Amphi 500")
        response = self.client.get(reverse("rooms:salle_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amphi 500")
        self.assertContains(response, "B201")
        self.assertNotContains(response, "Capacité")

    def test_update_affectation_inline_from_exam_completion(self):
        other_room = Salle.objects.create(nom="B202")
        response = self.client.post(
            reverse("exams:exam_room_update", args=[self.exam.pk, self.affectation.pk]),
            {
                "salle": str(other_room.pk),
                "temps_majore": "on",
                "nb_surveillants_requis": "3",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.affectation.refresh_from_db()
        self.assertEqual(self.affectation.salle, other_room)
        self.assertEqual(self.affectation.nb_surveillants_requis, 3)
        self.assertTrue(self.affectation.temps_majore)
        self.assertContains(response, "Affectation salle mise à jour.")


class SalleValidationMessageTests(TestCase):
    def test_lock_range_message_is_attached_to_field(self):
        salle = Salle(
            nom="C101",
            heure_debut_verrouillage=time(14, 0),
            heure_fin_verrouillage=time(12, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            salle.full_clean()
        self.assertIn("heure_fin_verrouillage", ctx.exception.message_dict)


class AffectationSalleLockWindowTests(TestCase):
    def setUp(self):
        self.year = AnneeUniversitaire.objects.create(
            nom="2030/2031",
            date_debut=date(2030, 9, 1),
            date_fin=date(2031, 7, 31),
            is_active=True,
        )
        self.formation = Formation.objects.create(annee_universitaire=self.year, nom="Formation lock")
        self.ue = UE.objects.create(nom="UE Lock")
        self.formation.ues.add(self.ue)
        self.session = SessionExamen.objects.create(formation=self.formation, nom="Session lock")
        self.salle = Salle.objects.create(nom="Lock room")

    def test_lock_window_matches_exam_schedule_without_temps_majore(self):
        exam = Examen.objects.create(
            session=self.session,
            ue=self.ue,
            nom="Exam lock simple",
            date=date(2031, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
        )
        affectation = AffectationSalle.objects.create(
            examen=exam,
            salle=self.salle,
            nb_surveillants_requis=1,
        )
        self.assertEqual(timezone.localtime(affectation.lock_start_dt).time().replace(tzinfo=None), time(9, 0))
        self.assertEqual(timezone.localtime(affectation.lock_end_dt).time().replace(tzinfo=None), time(12, 0))

    def test_temps_majore_extends_lock_window_by_one_third(self):
        exam = Examen.objects.create(
            session=self.session,
            ue=self.ue,
            nom="Exam lock majore",
            date=date(2031, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
        )
        affectation = AffectationSalle.objects.create(
            examen=exam,
            salle=self.salle,
            nb_surveillants_requis=1,
            temps_majore=True,
        )
        self.assertEqual(timezone.localtime(affectation.lock_end_dt).time().replace(tzinfo=None), time(13, 0))

    def test_room_conflict_uses_extended_lock_window(self):
        first_exam = Examen.objects.create(
            session=self.session,
            ue=self.ue,
            nom="Exam 1",
            date=date(2031, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
        )
        AffectationSalle.objects.create(
            examen=first_exam,
            salle=self.salle,
            nb_surveillants_requis=1,
            temps_majore=True,
        )

        second_exam = Examen.objects.create(
            session=self.session,
            ue=self.ue,
            nom="Exam 2",
            date=date(2031, 1, 10),
            heure_debut=time(12, 30),
            heure_fin=time(14, 0),
        )
        conflicting_affectation = AffectationSalle(
            examen=second_exam,
            salle=self.salle,
            nb_surveillants_requis=1,
        )
        with self.assertRaises(ValidationError) as ctx:
            conflicting_affectation.full_clean()
        self.assertIn("salle", ctx.exception.message_dict)
