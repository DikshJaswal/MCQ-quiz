import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from mcq_quiz.throttle import RateLimit
from .models import QuizAttempt, Semester, Subject, Topic
from .services import GenerationError, generate_questions

logger = logging.getLogger(__name__)
SESSION_QUIZ = "quiz"          
SESSION_REVIEW = "last_review"  
LETTERS = "ABCD"

def home(request):
    years = {}
    for semester in Semester.objects.prefetch_related("subject_set"):
        years.setdefault(semester.year, []).append(semester)
    year_groups = [{"year": year, "semesters": sems} for year, sems in sorted(years.items())]
    return render(request, "mcq_app/home.html", {"year_groups": year_groups})

@login_required
def semester_subjects(request, semester_id):
    semester = get_object_or_404(Semester, pk=semester_id)
    subjects = semester.subject_set.prefetch_related("topics")
    return render(request, "mcq_app/semester_subjects.html", {
        "semester": semester,
        "subjects": subjects,
    })

@login_required
def subject_topics(request, semester_id, subject_id):
    subject = get_object_or_404(
        Subject.objects.select_related("semester"), pk=subject_id, semester_id=semester_id
    )
    return render(request, "mcq_app/subject_topics.html", {
        "semester": subject.semester,
        "subject": subject,
        "topics": subject.topics.all(),
    })

def _topic(topic_id):
    return get_object_or_404(Topic.objects.select_related("subject__semester"), pk=topic_id)

@login_required
def quiz_intro(request, topic_id):
    topic = _topic(topic_id)
    status = 200
    if request.method == "POST":
        limiter = RateLimit(
            "generate", settings.QUIZ_GENERATE_LIMIT, settings.QUIZ_GENERATE_WINDOW_SECONDS
        )
        if limiter.hit(str(request.user.pk)) > settings.QUIZ_GENERATE_LIMIT:
            minutes = max(1, settings.QUIZ_GENERATE_WINDOW_SECONDS // 60)
            messages.error(
                request,
                f"You've reached the limit of {settings.QUIZ_GENERATE_LIMIT} new quizzes "
                f"per {minutes} minutes. Please try again later.",
            )
            status = 429
        else:
            try:
                questions = generate_questions(topic.name, topic.subject.name)
            except GenerationError as exc:
                messages.error(request, str(exc))
                status = 503
            else:
                request.session[SESSION_QUIZ] = {"topic_id": topic.pk, "questions": questions}
                request.session.pop(SESSION_REVIEW, None)
                return redirect("mcq_app:quiz_take", topic_id=topic.pk)
    return render(request, "mcq_app/quiz_intro.html", {
        "topic": topic,
        "subject": topic.subject,
        "semester": topic.subject.semester,
        "question_count": settings.QUIZ_QUESTION_COUNT,
        "minutes": settings.QUIZ_TIME_LIMIT_SECONDS // 60,
        "attempts": QuizAttempt.objects.filter(user=request.user, topic=topic)[:5],
    }, status=status)

def _selected_index(post, i, option_count):
    raw = post.get(f"q{i}", "")
    if raw.isdigit() and int(raw) < option_count:
        return int(raw)
    return None

@login_required
def quiz_take(request, topic_id):
    topic = _topic(topic_id)
    quiz = request.session.get(SESSION_QUIZ)
    if not quiz or quiz.get("topic_id") != topic.pk:
        messages.info(request, "Start a quiz to begin.")
        return redirect("mcq_app:quiz_intro", topic_id=topic.pk)
    questions = quiz["questions"]
    if request.method == "POST":
        items, correct = [], 0
        for i, q in enumerate(questions):
            selected = _selected_index(request.POST, i, len(q["options"]))
            is_correct = selected == q["answer"]
            correct += is_correct
            items.append({
                "number": i + 1,
                "question": q["question"],
                "difficulty": q["difficulty"],
                "explanation": q["explanation"],
                "status": "skipped" if selected is None else ("correct" if is_correct else "wrong"),
                "options": [
                    {
                        "letter": LETTERS[n],
                        "text": text,
                        "is_correct": n == q["answer"],
                        "is_selected": n == selected,
                    }
                    for n, text in enumerate(q["options"])
                ],
            })
        attempt = QuizAttempt.objects.create(
            user=request.user, topic=topic, score=correct, total_questions=len(questions)
        )
        request.session[SESSION_REVIEW] = {"attempt_id": attempt.pk, "items": items}
        request.session.pop(SESSION_QUIZ, None) 
        return redirect("mcq_app:quiz_results", attempt_id=attempt.pk)
    display = [
        {
            "number": i + 1,
            "index": i,
            "question": q["question"],
            "difficulty": q["difficulty"],
            "options": [{"letter": LETTERS[n], "value": n, "text": t} for n, t in enumerate(q["options"])],
        }
        for i, q in enumerate(questions)
    ]
    return render(request, "mcq_app/quiz_take.html", {
        "topic": topic,
        "subject": topic.subject,
        "semester": topic.subject.semester,
        "questions": display,
        "total": len(display),
        "time_limit": settings.QUIZ_TIME_LIMIT_SECONDS,
    })

@login_required
def quiz_results(request, attempt_id):
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("topic__subject__semester"),
        pk=attempt_id,
        user=request.user,
    )
    review = request.session.get(SESSION_REVIEW)
    items = review["items"] if review and review.get("attempt_id") == attempt.pk else None
    topic = attempt.topic
    skipped = sum(1 for item in items if item["status"] == "skipped") if items else 0
    return render(request, "mcq_app/quiz_results.html", {
        "attempt": attempt,
        "topic": topic,
        "subject": topic.subject,
        "semester": topic.subject.semester,
        "items": items,
        "skipped": skipped,
        "wrong": attempt.total_questions - attempt.score - skipped,
        "history": QuizAttempt.objects.filter(user=request.user, topic=topic)[:8],
    })