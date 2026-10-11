import json
import random
from io import StringIO
from pathlib import Path
from unittest import mock
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from accounts.models import User
from . import services
from .models import QuizAttempt, Semester, Subject, Topic
from .services import GenerationError

EXPLANATION = "UNIQUE-EXPLANATION-TEXT-12345"

def make_questions(n=15):
    """Questions in the shape services.generate_questions() returns (answer is always index 1)."""
    return [
        {
            "question": f"Question number {i}?",
            "options": [f"wrong-a-{i}", f"right-{i}", f"wrong-c-{i}", f"wrong-d-{i}"],
            "answer": 1,
            "difficulty": "GATE",
            "explanation": EXPLANATION,
        }
        for i in range(n)
    ]

class ParseQuestionTests(SimpleTestCase):
    def good(self, **overrides):
        item = {
            "question": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "answer_index": 1,
            "difficulty": "gate",
            "explanation": "Because.",
        }
        item.update(overrides)
        return item
    def parse(self, payload):
        return services.parse_questions(payload if isinstance(payload, str) else json.dumps(payload),
                                        rng=random.Random(1))
    def test_valid_question_is_kept_and_correct_answer_follows_shuffle(self):
        (q,) = self.parse([self.good()])
        self.assertEqual(q["options"][q["answer"]], "4")
        self.assertEqual(sorted(q["options"]), ["3", "4", "5", "6"])
        self.assertEqual(q["difficulty"], "GATE")
    def test_code_fences_and_wrapper_object_are_tolerated(self):
        raw = "```json\n" + json.dumps({"questions": [self.good()]}) + "\n```"
        self.assertEqual(len(self.parse(raw)), 1)
    def test_answer_by_text_or_letter_fallback(self):
        a = self.good(); del a["answer_index"]; a["answer"] = "4"
        b = self.good(); del b["answer_index"]; b["answer"] = "B"
        for item in (a, b):
            (q,) = self.parse([item])
            self.assertEqual(q["options"][q["answer"]], "4")
    def test_malformed_items_are_dropped(self):
        bad = [
            self.good(options=["a", "b", "c"]),                   
            self.good(options=["a", "a", "b", "c"]),              
            self.good(options=["a", "", "b", "c"]),               
            self.good(answer_index=7),                            
            self.good(answer_index=True),                         
            self.good(question=""),                               
            self.good(question="x" * 5000),                     
            "not a dict",
            {"question": "no options"},
        ]
        self.assertEqual(self.parse(bad), [])
    def test_unknown_difficulty_defaults(self):
        (q,) = self.parse([self.good(difficulty="Impossible")])
        self.assertEqual(q["difficulty"], "University")
    def test_garbage_returns_empty_list(self):
        for raw in ("", "not json", "42", "null", '{"questions": 5}'):
            self.assertEqual(self.parse(raw), [], raw)
    def test_html_is_kept_as_text_not_executed(self):
        (q,) = self.parse([self.good(question="<script>alert(1)</script>")])
        self.assertIn("<script>", q["question"]) 

class GenerateQuestionsTests(TestCase):
    @override_settings(GEMINI_API_KEY="")
    def test_missing_api_key_gives_friendly_error(self):
        with self.assertRaises(GenerationError):
            services.generate_questions("Topic", "Subject")
    @override_settings(GEMINI_API_KEY="test-key")
    def test_api_failure_does_not_leak_details(self):
        with mock.patch.object(services, "_call_gemini", side_effect=RuntimeError("secret internal detail")):
            with self.assertRaises(GenerationError) as ctx:
                services.generate_questions("Topic", "Subject")
        self.assertNotIn("secret", str(ctx.exception))
    @override_settings(GEMINI_API_KEY="test-key", QUIZ_QUESTION_COUNT=6)
    def test_too_few_valid_questions_is_an_error(self):
        raw = json.dumps([{"question": "q", "options": ["a", "b", "c", "d"], "answer_index": 0}])
        with mock.patch.object(services, "_call_gemini", return_value=raw):
            with self.assertRaises(GenerationError):
                services.generate_questions("Topic", "Subject")
    @override_settings(GEMINI_API_KEY="test-key", QUIZ_QUESTION_COUNT=6)
    def test_success_path(self):
        raw = json.dumps([
            {"question": f"q{i}", "options": ["a", "b", "c", "d"], "answer_index": 0,
             "difficulty": "GATE", "explanation": "e"} for i in range(8)
        ])
        with mock.patch.object(services, "_call_gemini", return_value=raw):
            questions = services.generate_questions("Topic", "Subject")
        self.assertEqual(len(questions), 6)

@override_settings(SECURE_SSL_REDIRECT=False, QUIZ_QUESTION_COUNT=15)
class QuizFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.semester = Semester.objects.create(number=1, name="Semester 1")
        cls.subject = Subject.objects.create(semester=cls.semester, name="Physics", description="Physics course")
        cls.topic = Topic.objects.create(subject=cls.subject, name="Optics", description="Light")
        cls.user = User.objects.create_user("alice", "alice@example.com", "correct-horse-battery-9")
        cls.other = User.objects.create_user("mallory", "mallory@example.com", "correct-horse-battery-9")
    def setUp(self):
        cache.clear()
        self.client.force_login(self.user)
    def start_quiz(self, questions=None):
        with mock.patch("mcq_app.views.generate_questions", return_value=questions or make_questions()):
            return self.client.post(reverse("mcq_app:quiz_intro", args=[self.topic.pk]))
    def test_home_is_public_and_lists_semesters_from_database(self):
        self.client.logout()
        resp = self.client.get(reverse("mcq_app:home"))
        self.assertContains(resp, "Semester 1")
        self.assertContains(resp, "Physics")
    def test_browsing_requires_login(self):
        self.client.logout()
        for url in (
            reverse("mcq_app:semester_subjects", args=[self.semester.pk]),
            reverse("mcq_app:quiz_intro", args=[self.topic.pk]),
            reverse("mcq_app:quiz_take", args=[self.topic.pk]),
        ):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, url)
            self.assertTrue(resp["Location"].startswith(reverse("login")), url)
    def test_drill_down_pages_render(self):
        for url in (
            reverse("mcq_app:semester_subjects", args=[self.semester.pk]),
            reverse("mcq_app:subject_topics", args=[self.semester.pk, self.subject.pk]),
            reverse("mcq_app:quiz_intro", args=[self.topic.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)
    def test_unknown_ids_404(self):
        self.assertEqual(self.client.get(reverse("mcq_app:semester_subjects", args=[999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("mcq_app:subject_topics", args=[self.semester.pk, 999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("mcq_app:quiz_intro", args=[999])).status_code, 404)
    def test_subject_must_belong_to_the_semester_in_the_url(self):
        other_sem = Semester.objects.create(number=2, name="Semester 2")
        resp = self.client.get(reverse("mcq_app:subject_topics", args=[other_sem.pk, self.subject.pk]))
        self.assertEqual(resp.status_code, 404)
    def test_generation_stores_quiz_server_side_and_redirects(self):
        resp = self.start_quiz()
        self.assertRedirects(resp, reverse("mcq_app:quiz_take", args=[self.topic.pk]))
        self.assertEqual(len(self.client.session["quiz"]["questions"]), 15)
    def test_generation_failure_shows_friendly_message(self):
        with mock.patch("mcq_app.views.generate_questions", side_effect=GenerationError("Try again later.")):
            resp = self.client.post(reverse("mcq_app:quiz_intro", args=[self.topic.pk]))
        self.assertEqual(resp.status_code, 503)
        self.assertContains(resp, "Try again later.", status_code=503)
        self.assertNotIn("quiz", self.client.session)
    def test_quiz_page_never_leaks_answers_or_explanations(self):
        self.start_quiz()
        html = self.client.get(reverse("mcq_app:quiz_take", args=[self.topic.pk])).content.decode()
        self.assertIn("Question number 0?", html)
        self.assertIn("right-0", html)            
        self.assertNotIn(EXPLANATION, html)      
        self.assertNotIn("answer_index", html)
        self.assertNotIn('"answer"', html)
    def test_taking_without_generating_redirects_to_intro(self):
        resp = self.client.get(reverse("mcq_app:quiz_take", args=[self.topic.pk]))
        self.assertRedirects(resp, reverse("mcq_app:quiz_intro", args=[self.topic.pk]))
    def test_quiz_for_other_topic_is_not_reused(self):
        other = Topic.objects.create(subject=self.subject, name="Mechanics")
        self.start_quiz()
        resp = self.client.get(reverse("mcq_app:quiz_take", args=[other.pk]))
        self.assertRedirects(resp, reverse("mcq_app:quiz_intro", args=[other.pk]))
    def submit(self, answers):
        return self.client.post(reverse("mcq_app:quiz_take", args=[self.topic.pk]), answers)
    def test_grading_counts_correct_wrong_and_skipped(self):
        self.start_quiz()
        answers = {f"q{i}": "1" for i in range(10)}          
        answers.update({f"q{i}": "0" for i in range(10, 13)}) 
        resp = self.submit(answers)
        attempt = QuizAttempt.objects.get()
        self.assertRedirects(resp, reverse("mcq_app:quiz_results", args=[attempt.pk]))
        self.assertEqual((attempt.score, attempt.total_questions, attempt.user), (10, 15, self.user))
        self.assertEqual(attempt.percentage, 67)
        page = self.client.get(reverse("mcq_app:quiz_results", args=[attempt.pk]))
        self.assertContains(page, EXPLANATION)
        self.assertEqual(page.context["wrong"], 3)
        self.assertEqual(page.context["skipped"], 2)
    def test_tampered_answer_values_are_treated_as_skipped(self):
        self.start_quiz()
        resp = self.submit({"q0": "99", "q1": "-1", "q2": "abc", "q3": "<script>"})
        attempt = QuizAttempt.objects.get()
        self.assertEqual(attempt.score, 0)
        page = self.client.get(resp["Location"])
        self.assertEqual(page.context["skipped"], 15)
    def test_quiz_can_only_be_submitted_once(self):
        self.start_quiz()
        self.submit({"q0": "1"})
        resp = self.submit({f"q{i}": "1" for i in range(15)})  
        self.assertRedirects(resp, reverse("mcq_app:quiz_intro", args=[self.topic.pk]))
        self.assertEqual(QuizAttempt.objects.count(), 1)
    def test_users_cannot_view_each_others_attempts(self):
        self.start_quiz()
        attempt_url = self.submit({"q0": "1"})["Location"]
        self.client.logout()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(attempt_url).status_code, 404)
    def test_review_is_only_shown_for_the_attempt_it_belongs_to(self):
        self.start_quiz()
        self.submit({"q0": "1"})
        old = QuizAttempt.objects.create(user=self.user, topic=self.topic, score=1, total_questions=2)
        page = self.client.get(reverse("mcq_app:quiz_results", args=[old.pk]))
        self.assertNotContains(page, EXPLANATION)
        self.assertContains(page, "only available right after")
    def test_ai_generated_html_is_escaped(self):
        questions = make_questions()
        questions[0]["question"] = "<img src=x onerror=alert(1)>"
        questions[0]["explanation"] = "<script>alert('xss')</script>"
        self.start_quiz(questions)
        take = self.client.get(reverse("mcq_app:quiz_take", args=[self.topic.pk])).content.decode()
        self.assertNotIn("<img src=x", take)
        self.assertIn("&lt;img src=x", take)
        url = self.submit({})["Location"]
        results = self.client.get(url).content.decode()
        self.assertNotIn("<script>alert", results)
        self.assertIn("&lt;script&gt;alert", results)
    @override_settings(QUIZ_GENERATE_LIMIT=2)
    def test_generation_is_rate_limited_per_user(self):
        with mock.patch("mcq_app.views.generate_questions", return_value=make_questions()) as gen:
            url = reverse("mcq_app:quiz_intro", args=[self.topic.pk])
            self.client.post(url)
            self.client.post(url)
            resp = self.client.post(url)
            self.assertEqual(resp.status_code, 429)
            self.assertEqual(gen.call_count, 2)
            self.client.force_login(self.other)
            self.assertEqual(self.client.post(url).status_code, 302)
    def test_debug_and_legacy_endpoints_are_gone(self):
        for path in ("/debug-urls/", "/generate-explanation/", "/get-explanation/1/", "/submit-quiz/", "/save-answer/"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
    def test_profile_shows_real_stats(self):
        QuizAttempt.objects.create(user=self.user, topic=self.topic, score=9, total_questions=10)
        QuizAttempt.objects.create(user=self.user, topic=self.topic, score=7, total_questions=10)
        page = self.client.get(reverse("profile"))
        self.assertEqual(page.context["attempt_count"], 2)
        self.assertEqual(page.context["accuracy"], 80)
        self.assertEqual(page.context["topic_count"], 1)

class ImportDataTests(TestCase):
    def test_import_is_idempotent_and_handles_unicode(self):
        call_command("import_data", stdout=StringIO())
        counts = (Semester.objects.count(), Subject.objects.count(), Topic.objects.count())
        self.assertEqual(counts, (8, 24, 72))
        call_command("import_data", stdout=StringIO())
        self.assertEqual((Semester.objects.count(), Subject.objects.count(), Topic.objects.count()), counts)
        self.assertTrue(Topic.objects.filter(description__contains="Shor’s").exists())
    def test_missing_file_gives_clean_error(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("import_data", str(Path(settings.BASE_DIR) / "nope.json"))

@override_settings(SECURE_SSL_REDIRECT=False)
class SecurityHeaderTests(TestCase):
    def test_csp_is_strict_on_site_pages(self):
        csp = self.client.get(reverse("mcq_app:home"))["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("http", csp) 
    def test_pages_contain_no_inline_script_or_style(self):
        html = self.client.get(reverse("mcq_app:home")).content.decode()
        for needle in ("<style", " style=", " onclick=", "<script>"):
            self.assertNotIn(needle, html)
    def test_clickjacking_and_sniffing_headers(self):
        resp = self.client.get(reverse("mcq_app:home"))
        self.assertEqual(resp["X-Frame-Options"], "DENY")
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")
    def test_admin_is_not_given_the_strict_policy(self):
        self.assertNotIn("Content-Security-Policy", self.client.get("/admin/login/"))
    def test_404_page_renders(self):
        with override_settings(DEBUG=False):
            resp = self.client.get("/definitely-not-a-page/")
        self.assertEqual(resp.status_code, 404)

@override_settings(SECURE_SSL_REDIRECT=False)
class LayoutConsistencyTests(TestCase):
    """Every page shares one navbar (same logo, same links) and one footer."""
    @classmethod
    def setUpTestData(cls):
        call_command("import_data", stdout=StringIO())
        cls.user = User.objects.create_user("alice", "alice@example.com", "correct-horse-battery-9")
    @staticmethod
    def navbar(html):
        import re
        nav = re.search(r'<nav class="navbar".*?</nav>', html, re.S).group(0)
        nav = re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", nav)
        return nav.replace(' class="active" aria-current="page"', "")
    @staticmethod
    def footer(html):
        import re
        return re.search(r"<footer>.*?</footer>", html, re.S).group(0)
    def urls(self):
        topic = Topic.objects.first()
        return [
            reverse("mcq_app:home"),
            reverse("mcq_app:semester_subjects", args=[topic.subject.semester_id]),
            reverse("mcq_app:subject_topics", args=[topic.subject.semester_id, topic.subject_id]),
            reverse("mcq_app:quiz_intro", args=[topic.pk]),
            reverse("profile"),
            reverse("edit_profile"),
            reverse("password_change"),
        ]
    def test_same_navbar_and_footer_when_logged_in(self):
        self.client.force_login(self.user)
        navs, footers = set(), set()
        for url in self.urls():
            html = self.client.get(url).content.decode()
            navs.add(self.navbar(html)); footers.add(self.footer(html))
        self.assertEqual(len(navs), 1)
        self.assertEqual(len(footers), 1)
    def test_same_navbar_and_footer_when_logged_out(self):
        navs, footers = set(), set()
        for url in [reverse("mcq_app:home"), reverse("login"), reverse("signup"),
                    reverse("password_reset"), "/no-such-page/"]:
            html = self.client.get(url).content.decode()
            navs.add(self.navbar(html)); footers.add(self.footer(html))
        self.assertEqual(len(navs), 1)
        self.assertEqual(len(footers), 1)
    def test_nav_has_no_dead_tests_link(self):
        html = self.client.get(reverse("mcq_app:home")).content.decode()
        nav = self.navbar(html)
        self.assertNotIn("Tests", nav)
        self.assertNotIn('href="#"', nav)
        self.assertIn("CSE MCQ Portal", nav)
    def test_current_page_is_highlighted_in_nav(self):
        self.client.force_login(self.user)
        home = self.client.get(reverse("mcq_app:home")).content.decode()
        profile = self.client.get(reverse("profile")).content.decode()
        self.assertRegex(home, r'<a href="/" class="active" aria-current="page">Home</a>')
        self.assertRegex(profile, r'class="active" aria-current="page">Profile</a>')
    def test_subject_and_topic_pages_use_the_semester_card_design(self):
        self.client.force_login(self.user)
        topic = Topic.objects.first()
        topics_page = self.client.get(
            reverse("mcq_app:subject_topics", args=[topic.subject.semester_id, topic.subject_id])
        ).content.decode()
        self.assertEqual(topics_page.count('class="semester-card"'), topic.subject.topics.count())
        subjects_page = self.client.get(
            reverse("mcq_app:semester_subjects", args=[topic.subject.semester_id])
        ).content.decode()
        self.assertEqual(subjects_page.count('class="semester-card"'), 3)