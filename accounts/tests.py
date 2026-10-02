import re
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import LoginCode, User


def make_user(email, **extra):
    extra.setdefault("full_name", email.split("@")[0].title())
    extra.setdefault("research_topic", "Earth science")
    extra.setdefault("career_stage", "postdoc")
    return User.objects.create_user(email, **extra)


class LoginFlowTests(TestCase):
    def setUp(self):
        self.user = make_user("ana@test.org")

    def request_code(self, email="ana@test.org"):
        response = self.client.post(reverse("accounts:login"), {"email": email})
        self.assertRedirects(response, reverse("accounts:verify"))
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1) if mail.outbox else None

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("mentoring:home"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next=/")

    def test_login_with_code(self):
        code = self.request_code()
        response = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertRedirects(response, reverse("mentoring:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_email_is_case_insensitive(self):
        self.request_code("Ana@Test.org")
        self.assertEqual(len(mail.outbox), 1)

    def test_code_cannot_be_reused(self):
        code = self.request_code()
        self.client.post(reverse("accounts:verify"), {"code": code})
        self.client.post(reverse("accounts:logout"))
        self.client.post(reverse("accounts:login"), {"email": "ana@test.org"})
        response = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertContains(response, "invalid or has expired")

    def test_uninvited_email_gets_same_response_and_no_email(self):
        code = self.request_code("stranger@test.org")
        self.assertIsNone(code)
        self.assertEqual(len(mail.outbox), 0)
        response = self.client.post(reverse("accounts:verify"), {"code": "123456"})
        self.assertContains(response, "invalid or has expired")

    def test_inactive_user_gets_no_code(self):
        self.user.is_active = False
        self.user.save()
        self.request_code()
        self.assertEqual(len(mail.outbox), 0)

    def test_expired_code_is_rejected(self):
        code = self.request_code()
        LoginCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertContains(response, "invalid or has expired")

    def test_code_locks_after_too_many_attempts(self):
        code = self.request_code()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.client.post(reverse("accounts:verify"), {"code": wrong})
        response = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertContains(response, "invalid or has expired")

    def test_resend_is_throttled(self):
        self.request_code()
        self.request_code()
        self.assertEqual(len(mail.outbox), 1)


class OnboardingTests(TestCase):
    def test_incomplete_profile_is_sent_to_welcome(self):
        user = User.objects.create_user("new@test.org")
        self.client.force_login(user)
        response = self.client.get(reverse("mentoring:home"))
        self.assertRedirects(response, reverse("accounts:welcome"))

        response = self.client.post(
            reverse("accounts:welcome"),
            {"full_name": "New Person", "research_topic": "Glaciers", "career_stage": "phd"},
        )
        self.assertRedirects(response, reverse("mentoring:home"))
        user.refresh_from_db()
        self.assertTrue(user.profile_completed)


class InviteCommandTests(TestCase):
    def test_invite_creates_users_once(self):
        out = StringIO()
        call_command("invite", "A@test.org", "b@test.org", "not-an-email", stdout=out, stderr=StringIO())
        call_command("invite", "a@test.org", stdout=out)
        self.assertEqual(sorted(User.objects.values_list("email", flat=True)), ["a@test.org", "b@test.org"])
        self.assertFalse(User.objects.get(email="a@test.org").has_usable_password())
