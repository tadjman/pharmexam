from datetime import date, time

from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError

from academics.models import AnneeUniversitaire, UE, UP
from accounts.models import RoleUtilisateur, User
from assignments.models import Surveillance
from exams.models import Examen, SessionExamen
from rooms.models import AffectationSalle, Salle


class RoomDeleteViewTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_room_delete",
            password="pass",
            role=RoleUtilisateur.SCOLARITE,
            is_staff=True,
        )
        self.teacher = User.objects.create_user(
            username="teacher_room_delete",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )
        self.year = AnneeUniversitaire.objects.create(
            nom="2029/2030",
            date_debut=date(2029, 9, 1),
            date_fin=date(2030, 7, 31),
            is_active=True,
        )
        self.session = SessionExamen.objects.create(
            annee_universitaire=self.year,
            nom="Session room delete",
            date_debut=date(2030, 1, 1),
            date_fin=date(2030, 1, 31),
        )
        ue = UE.objects.create(nom="UE Room Delete")
        ue.responsables.add(self.teacher)
        up = UP.objects.create(ue=ue, nom="UP Room Delete", matiere="RD")
        self.exam = Examen.objects.create(
            session=self.session,
            up=up,
            nom="Exam room delete",
            date=date(2030, 1, 15),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=20,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=self.teacher,
        )
        self.salle = Salle.objects.create(nom="B201", capacite_max=30)
        AffectationSalle.objects.create(examen=self.exam, salle=self.salle)

        self.client.force_login(self.admin_user)
        session = self.client.session
        session["active_year_id"] = str(self.year.pk)
        session.save()

    def test_delete_protected_salle_returns_message_instead_of_500(self):
        response = self.client.post(reverse("rooms:salle_delete", args=[self.salle.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible")
        self.assertTrue(Salle.objects.filter(pk=self.salle.pk).exists())

    def test_delete_affectation_from_exam_completion_blocks_if_capacity_becomes_insufficient(self):
        affectation = AffectationSalle.objects.get(examen=self.exam, salle=self.salle)
        response = self.client.post(
            reverse("exams:exam_complete", args=[self.exam.pk]),
            {"action": "delete_room", "room_id": str(affectation.pk)},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suppression impossible")
        self.assertTrue(AffectationSalle.objects.filter(pk=affectation.pk).exists())

    def test_legacy_room_assignment_route_is_not_public_anymore(self):
        response = self.client.get(f"/examens/{self.exam.pk}/salles/")
        self.assertEqual(response.status_code, 404)

    def test_room_list_filters_by_query_and_capacity(self):
        Salle.objects.create(nom="Amphi 500", capacite_max=500)
        response = self.client.get(
            reverse("rooms:salle_list"),
            {"q": "Amphi", "capacite_min": "100"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amphi 500")
        self.assertNotContains(response, "B201")

    def test_update_affectation_inline_from_exam_completion(self):
        affectation = AffectationSalle.objects.get(examen=self.exam, salle=self.salle)
        other_room = Salle.objects.create(nom="B202", capacite_max=40)
        response = self.client.post(
            reverse("exams:exam_complete", args=[self.exam.pk]),
            {
                "action": "update_room",
                "room_id": str(affectation.pk),
                f"room-{affectation.pk}-salle": str(other_room.pk),
                f"room-{affectation.pk}-is_tiers_temps": "on",
                f"room-{affectation.pk}-capacite_reservee": "25",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        affectation.refresh_from_db()
        self.assertEqual(affectation.salle, other_room)
        self.assertEqual(affectation.capacite_reservee, 25)
        self.assertTrue(affectation.is_tiers_temps)
        self.assertContains(response, "Affectation salle mise à jour.")


class AffectationValidationMessageTests(TestCase):
    def test_capacity_message_is_attached_to_field(self):
        teacher = User.objects.create_user(
            username="teacher_room_message",
            password="pass",
            role=RoleUtilisateur.ENSEIGNANT,
        )
        year = AnneeUniversitaire.objects.create(
            nom="2030/2031",
            date_debut=date(2030, 9, 1),
            date_fin=date(2031, 7, 31),
            is_active=True,
        )
        session = SessionExamen.objects.create(
            annee_universitaire=year,
            nom="Session validation",
            date_debut=date(2031, 1, 1),
            date_fin=date(2031, 1, 31),
        )
        ue = UE.objects.create(nom="UE Validation")
        ue.responsables.add(teacher)
        up = UP.objects.create(ue=ue, nom="UP Validation", matiere="VAL")
        exam = Examen.objects.create(
            session=session,
            up=up,
            nom="Exam validation",
            date=date(2031, 1, 10),
            heure_debut=time(9, 0),
            heure_fin=time(11, 0),
            nb_eleves=10,
            nb_eleves_tiers_temps=0,
            nb_surveillants_requis=1,
            responsable=teacher,
        )
        room = Salle.objects.create(nom="C101", capacite_max=20)
        affectation = AffectationSalle(
            examen=exam,
            salle=room,
            capacite_reservee=30,
        )
        with self.assertRaises(ValidationError) as ctx:
            affectation.full_clean()
        self.assertIn("capacite_reservee", ctx.exception.message_dict)
