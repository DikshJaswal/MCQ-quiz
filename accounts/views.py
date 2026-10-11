from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from mcq_app.models import QuizAttempt
from mcq_quiz.throttle import RateLimit, client_ip
from .forms import LoginForm, ProfileForm, SignupForm


class ThrottledLoginView(LoginView):
    """Django's LoginView (safe ``next`` handling included) plus brute-force protection."""
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True
    def _limiter(self):
        return RateLimit("login", settings.LOGIN_MAX_FAILURES, settings.LOGIN_LOCKOUT_SECONDS)
    def _identity(self):
        username = self.request.POST.get("username", "").strip().lower()
        return f"{client_ip(self.request)}|{username}"
    def post(self, request, *args, **kwargs):
        if self._limiter().is_blocked(self._identity()):
            context = self.get_context_data(form=self.form_class(request), throttled=True)
            return self.render_to_response(context, status=429)
        return super().post(request, *args, **kwargs)
    def form_invalid(self, form):
        self._limiter().hit(self._identity())
        return super().form_invalid(form)
    def form_valid(self, form):
        self._limiter().reset(self._identity())
        return super().form_valid(form)

class ThrottledPasswordResetView(PasswordResetView):
    """Limits reset e-mails per client IP so the form can't be used to spam inboxes.
    Over-limit requests look identical to successful ones (no information leak)."""
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")
    def form_valid(self, form):
        limiter = RateLimit("pwreset", settings.PASSWORD_RESET_MAX_REQUESTS, 60 * 60)
        if limiter.hit(client_ip(self.request)) > settings.PASSWORD_RESET_MAX_REQUESTS:
            return HttpResponseRedirect(self.get_success_url())
        return super().form_valid(form)

def signup(request):
    if request.user.is_authenticated:
        return redirect("mcq_app:home")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! Your account is ready.")
            return redirect("mcq_app:home")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})

@login_required
def profile(request):
    attempts = QuizAttempt.objects.filter(user=request.user)
    totals = attempts.aggregate(
        count=Count("id"), correct=Sum("score"), asked=Sum("total_questions"),
        topics=Count("topic", distinct=True),
    )
    accuracy = round(100 * totals["correct"] / totals["asked"]) if totals["asked"] else None
    return render(request, "accounts/profile.html", {
        "attempt_count": totals["count"],
        "topic_count": totals["topics"],
        "accuracy": accuracy,
        "recent_attempts": attempts.select_related("topic", "topic__subject")[:5],
    })

@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/edit_profile.html", {"form": form})