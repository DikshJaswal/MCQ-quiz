from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import User

STRONG = "correct-horse-battery-9"

@override_settings(SECURE_SSL_REDIRECT=False)
class AccountsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("alice", "alice@example.com", STRONG)
    def test_signup_creates_user_and_logs_in(self):
        resp = self.client.post(reverse("signup"), {
            "username": "bob", "email": "Bob@Example.com",
            "password1": STRONG, "password2": STRONG,
        })
        self.assertRedirects(resp, reverse("mcq_app:home"))
        bob = User.objects.get(username="bob")
        self.assertEqual(bob.email, "bob@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), bob.pk)
    def test_signup_rejects_duplicate_email_case_insensitively(self):
        resp = self.client.post(reverse("signup"), {
            "username": "alice2", "email": "ALICE@example.com",
            "password1": STRONG, "password2": STRONG,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "already exists")
        self.assertFalse(User.objects.filter(username="alice2").exists())
    def test_signup_enforces_password_rules(self):
        for bad in ("short1", "1234567890", "password123"):
            resp = self.client.post(reverse("signup"), {
                "username": "carol", "email": "carol@example.com",
                "password1": bad, "password2": bad,
            })
            self.assertEqual(resp.status_code, 200, bad)
            self.assertFalse(User.objects.filter(username="carol").exists(), bad)
    def test_login_works(self):
        resp = self.client.post(reverse("login"), {"username": "alice", "password": STRONG})
        self.assertRedirects(resp, reverse("mcq_app:home"))
    def test_login_ignores_external_next_url(self):
        resp = self.client.post(reverse("login") + "?next=https://evil.example/", {
            "username": "alice", "password": STRONG, "next": "https://evil.example/",
        })
        self.assertRedirects(resp, reverse("mcq_app:home"), fetch_redirect_response=False)
    def test_login_honours_internal_next_url(self):
        target = reverse("profile")
        resp = self.client.post(reverse("login"), {
            "username": "alice", "password": STRONG, "next": target,
        })
        self.assertRedirects(resp, target)
    @override_settings(LOGIN_MAX_FAILURES=3)
    def test_login_is_throttled_after_repeated_failures(self):
        for _ in range(3):
            resp = self.client.post(reverse("login"), {"username": "alice", "password": "nope"})
            self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse("login"), {"username": "alice", "password": STRONG})
        self.assertEqual(resp.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
    @override_settings(LOGIN_MAX_FAILURES=3)
    def test_throttle_is_per_username(self):
        for _ in range(3):
            self.client.post(reverse("login"), {"username": "alice", "password": "nope"})
        User.objects.create_user("dave", "dave@example.com", STRONG)
        resp = self.client.post(reverse("login"), {"username": "dave", "password": STRONG})
        self.assertEqual(resp.status_code, 302)
    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
    def test_profile_requires_login(self):
        resp = self.client.get(reverse("profile"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('profile')}")
    def test_profile_and_edit(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("profile")), "alice@example.com")
        resp = self.client.post(reverse("edit_profile"), {
            "username": "alice", "email": "new@example.com", "first_name": "Alice", "last_name": "A",
        })
        self.assertRedirects(resp, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
    def test_edit_profile_cannot_steal_another_users_email(self):
        User.objects.create_user("erin", "erin@example.com", STRONG)
        self.client.force_login(self.user)
        resp = self.client.post(reverse("edit_profile"), {
            "username": "alice", "email": "Erin@example.com", "first_name": "", "last_name": "",
        })
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.com")
    def test_password_reset_sends_email_using_request_host(self):
        resp = self.client.post(reverse("password_reset"), {"email": "alice@example.com"})
        self.assertRedirects(resp, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)
        self.assertIn("testserver", mail.outbox[0].body)
    def test_password_reset_does_not_reveal_unknown_emails(self):
        resp = self.client.post(reverse("password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(resp, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
    @override_settings(PASSWORD_RESET_MAX_REQUESTS=2)
    def test_password_reset_is_rate_limited(self):
        for _ in range(5):
            resp = self.client.post(reverse("password_reset"), {"email": "alice@example.com"})
            self.assertRedirects(resp, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 2)
