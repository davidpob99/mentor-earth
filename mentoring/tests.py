from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.tests import make_user

from . import services
from .models import MentorProfile, MentoringRelationship, Notification
from .services import MentoringError


def make_mentor(user, capacity=2, **extra):
    extra.setdefault("contact_preference", "email")
    extra.setdefault("superpower", "coffee")
    return services.become_mentor(user, capacity=capacity, **extra)


class ServiceTests(TestCase):
    def setUp(self):
        self.ana = make_user("ana@test.org")
        self.ben = make_user("ben@test.org")
        self.cris = make_user("cris@test.org")
        self.dan = make_user("dan@test.org")
        make_mentor(self.ana)

    def available(self, user):
        return [p.user for p in services.available_mentors(user)]

    def test_choosing_creates_active_relationship_and_notifies_both(self):
        rel = services.choose_mentor(self.ben, self.ana)
        self.assertTrue(rel.is_active)
        self.assertEqual(
            set(Notification.objects.values_list("recipient__email", "kind")),
            {("ana@test.org", "match_created"), ("ben@test.org", "match_created")},
        )

    def test_capacity_is_enforced(self):
        services.choose_mentor(self.ben, self.ana)
        self.assertEqual(self.available(self.dan), [self.ana])
        services.choose_mentor(self.cris, self.ana)
        self.assertEqual(self.available(self.dan), [])
        with self.assertRaises(MentoringError):
            services.choose_mentor(self.dan, self.ana)
        self.assertEqual(MentoringRelationship.objects.count(), 2)

    def test_capacity_of_one(self):
        make_mentor(self.ana, capacity=1)
        services.choose_mentor(self.ben, self.ana)
        with self.assertRaises(MentoringError):
            services.choose_mentor(self.cris, self.ana)

    def test_capacity_above_program_maximum_is_rejected(self):
        with self.assertRaises(MentoringError):
            make_mentor(self.ben, capacity=3)

    def test_cannot_lower_capacity_below_current_mentees(self):
        services.choose_mentor(self.ben, self.ana)
        services.choose_mentor(self.cris, self.ana)
        with self.assertRaises(MentoringError):
            make_mentor(self.ana, capacity=1)

    def test_cannot_choose_self_or_a_non_mentor(self):
        with self.assertRaises(MentoringError):
            services.choose_mentor(self.ana, self.ana)
        with self.assertRaises(MentoringError):
            services.choose_mentor(self.ben, self.cris)

    def test_one_mentor_at_a_time(self):
        make_mentor(self.cris)
        services.choose_mentor(self.ben, self.ana)
        with self.assertRaises(MentoringError):
            services.choose_mentor(self.ben, self.cris)

    def test_database_rejects_second_active_mentor(self):
        make_mentor(self.cris)
        MentoringRelationship.objects.create(mentor=self.ana, mentee=self.ben)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MentoringRelationship.objects.create(mentor=self.cris, mentee=self.ben)

    def test_mentor_can_also_be_a_mentee(self):
        make_mentor(self.ben)
        services.choose_mentor(self.ana, self.ben)
        services.choose_mentor(self.cris, self.ana)
        self.assertEqual(services.current_mentor_relationship(self.ana).mentor, self.ben)

    def test_discovery_excludes_self_and_current_mentor(self):
        self.assertEqual(self.available(self.ana), [])
        services.choose_mentor(self.ben, self.ana)
        self.assertEqual(self.available(self.ben), [])
        self.assertEqual(self.available(self.cris), [self.ana])

    def test_discovery_filters(self):
        self.ana.research_topic = "Marine geology"
        self.ana.career_stage = "faculty"
        self.ana.save()
        find = lambda **kw: [p.user for p in services.available_mentors(self.ben, **kw)]
        self.assertEqual(find(research="geology"), [self.ana])
        self.assertEqual(find(research="biology"), [])
        self.assertEqual(find(stage="faculty"), [self.ana])
        self.assertEqual(find(stage="phd"), [])

    def test_pause_hides_mentor_but_keeps_relationships(self):
        services.choose_mentor(self.ben, self.ana)
        services.pause_mentoring(self.ana)
        self.assertEqual(self.available(self.cris), [])
        with self.assertRaises(MentoringError):
            services.choose_mentor(self.cris, self.ana)
        self.assertIsNotNone(services.current_mentor_relationship(self.ben))
        services.resume_mentoring(self.ana)
        self.assertEqual(self.available(self.cris), [self.ana])

    def test_ending_frees_the_place_and_notifies_the_other_party(self):
        make_mentor(self.ana, capacity=1)
        rel = services.choose_mentor(self.ben, self.ana)
        Notification.objects.all().delete()
        services.end_relationship(rel, self.ben, "goals")
        rel.refresh_from_db()
        self.assertEqual(rel.status, "ended")
        self.assertEqual(rel.ended_by, self.ben)
        self.assertEqual(rel.end_reason, "goals")
        self.assertIsNotNone(rel.ended_at)
        self.assertEqual(self.available(self.cris), [self.ana])
        self.assertEqual(
            list(Notification.objects.values_list("recipient__email", "kind")),
            [("ana@test.org", "match_ended")],
        )
        # The same pair can be matched again later; history is kept.
        services.choose_mentor(self.ben, self.ana)
        self.assertEqual(MentoringRelationship.objects.count(), 2)

    def test_outsider_cannot_end_a_relationship(self):
        rel = services.choose_mentor(self.ben, self.ana)
        with self.assertRaises(MentoringError):
            services.end_relationship(rel, self.cris)

    def test_stop_mentoring_ends_mentee_relationships_only(self):
        make_mentor(self.dan)
        services.choose_mentor(self.ana, self.dan)
        services.choose_mentor(self.ben, self.ana)
        services.choose_mentor(self.cris, self.ana)
        Notification.objects.all().delete()
        services.stop_mentoring(self.ana)
        self.assertIsNone(services.mentor_profile(self.ana))
        self.assertFalse(services.current_mentee_relationships(self.ana).exists())
        self.assertIsNotNone(services.current_mentor_relationship(self.ana))
        self.assertEqual(
            set(Notification.objects.values_list("recipient__email", "kind")),
            {("ben@test.org", "mentor_left"), ("cris@test.org", "mentor_left")},
        )
        self.assertEqual(self.available(self.ben), [self.dan])

    def test_rejoining_reuses_the_profile(self):
        services.stop_mentoring(self.ana)
        make_mentor(self.ana, capacity=1)
        self.assertEqual(MentorProfile.objects.filter(user=self.ana).count(), 1)
        self.assertEqual(self.available(self.ben), [self.ana])

    def test_leave_program_ends_everything(self):
        make_mentor(self.dan)
        services.choose_mentor(self.ana, self.dan)
        services.choose_mentor(self.ben, self.ana)
        services.leave_program(self.ana)
        self.assertFalse(MentoringRelationship.objects.filter(status="active").exists())
        self.assertIsNone(services.mentor_profile(self.ana))
        self.assertTrue(self.dan.notifications.filter(kind="match_ended").exists())
        self.assertTrue(self.ben.notifications.filter(kind="mentor_left").exists())


class ViewTests(TestCase):
    def setUp(self):
        self.ana = make_user("ana@test.org")
        self.ben = make_user("ben@test.org")
        self.cris = make_user("cris@test.org")
        self.client.force_login(self.ben)

    def test_home_offers_both_actions(self):
        response = self.client.get(reverse("mentoring:home"))
        self.assertContains(response, "Find a mentor")
        self.assertContains(response, "Become a mentor")

    def test_become_mentor_form(self):
        url = reverse("mentoring:mentor_join")
        data = {"capacity": 2, "contact_preference": "slack", "superpower": "other"}
        response = self.client.post(url, data)
        self.assertContains(response, "Add your Slack handle")
        self.assertContains(response, "Tell us your superpower")
        data |= {"slack_handle": "@ben", "superpower_other": "Naps"}
        self.assertRedirects(self.client.post(url, data), reverse("mentoring:profile"))
        profile = services.mentor_profile(self.ben)
        self.assertEqual(profile.superpower_display, "✨ Naps")
        self.assertContains(self.client.get(reverse("mentoring:home")), "You're a mentor")

    def test_full_lifecycle_through_views(self):
        make_mentor(self.ana, contact_preference="either", slack_handle="@ana")
        listing = self.client.get(reverse("mentoring:mentor_list"))
        self.assertContains(listing, "Ana")
        self.assertNotContains(listing, "ana@test.org")  # no contact details before matching

        response = self.client.post(reverse("mentoring:choose_mentor", args=[self.ana.pk]))
        self.assertRedirects(response, reverse("mentoring:profile"))
        profile_page = self.client.get(reverse("mentoring:profile"))
        self.assertContains(profile_page, "mailto:ana@test.org")
        self.assertContains(profile_page, "@ana")

        # The mentor sees an unread notification, which is marked read on viewing.
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse("mentoring:home")).context["unread_notifications"], 1)
        self.assertContains(self.client.get(reverse("mentoring:notifications")), "chose you as their mentor")
        self.assertEqual(self.client.get(reverse("mentoring:home")).context["unread_notifications"], 0)

        rel = MentoringRelationship.objects.get()
        end_url = reverse("mentoring:end_relationship", args=[rel.pk])
        self.assertContains(self.client.get(end_url), "End this mentoring relationship?")
        self.assertRedirects(self.client.post(end_url, {"reason": ""}), reverse("mentoring:profile"))
        rel.refresh_from_db()
        self.assertFalse(rel.is_active)
        self.assertEqual(self.ben.notifications.filter(kind="match_ended").count(), 1)

    def test_choosing_a_full_mentor_shows_an_error(self):
        make_mentor(self.ana, capacity=1)
        services.choose_mentor(self.cris, self.ana)
        response = self.client.post(reverse("mentoring:choose_mentor", args=[self.ana.pk]), follow=True)
        self.assertContains(response, "last place was just taken")
        self.assertIsNone(services.current_mentor_relationship(self.ben))

    def test_choose_requires_post(self):
        make_mentor(self.ana)
        response = self.client.get(reverse("mentoring:choose_mentor", args=[self.ana.pk]))
        self.assertEqual(response.status_code, 405)

    def test_cannot_end_someone_elses_relationship(self):
        make_mentor(self.ana)
        rel = services.choose_mentor(self.cris, self.ana)
        response = self.client.post(reverse("mentoring:end_relationship", args=[rel.pk]))
        self.assertEqual(response.status_code, 404)
        rel.refresh_from_db()
        self.assertTrue(rel.is_active)

    def test_random_pick_shows_at_most_three(self):
        for name in ("m1", "m2", "m3", "m4", "m5"):
            make_mentor(make_user(f"{name}@test.org"))
        response = self.client.get(reverse("mentoring:mentor_list"), {"random": 1})
        self.assertEqual(len(response.context["mentors"]), 3)

    def test_stop_and_leave_confirmations(self):
        make_mentor(self.ben)
        services.choose_mentor(self.cris, self.ben)
        self.assertContains(self.client.get(reverse("mentoring:stop_mentoring")), "Cris")
        self.assertRedirects(
            self.client.post(reverse("mentoring:leave_program")), reverse("mentoring:profile")
        )
        self.assertFalse(MentoringRelationship.objects.filter(status="active").exists())

    def test_staff_dashboard_is_staff_only(self):
        response = self.client.get(reverse("mentoring:staff_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.ben.is_staff = True
        self.ben.save()
        self.assertEqual(self.client.get(reverse("mentoring:staff_dashboard")).status_code, 200)
