from django.conf import settings
from django.db import models

class Semester(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    class Meta:
        ordering = ["number"]
    def __str__(self):
        return f"Semester {self.number}"
    @property
    def year(self) -> int:
        return (self.number + 1) // 2

class Subject(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    class Meta:
        unique_together = ("semester", "name")
        ordering = ["id"]
    def __str__(self):
        return f"{self.name} (Semester {self.semester.number})"

class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="topics")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    class Meta:
        unique_together = ("subject", "name")
        ordering = ["id"]
    def __str__(self):
        return f"{self.name} ({self.subject.name})"

class QuizAttempt(models.Model):
    """One finished quiz. ``score`` is the number of correct answers."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    score = models.PositiveSmallIntegerField()
    total_questions = models.PositiveSmallIntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-completed_at"]
    def __str__(self):
        return f"{self.user} - {self.topic.name}: {self.score}/{self.total_questions}"
    @property
    def percentage(self) -> int:
        if not self.total_questions:
            return 0
        return round(100 * self.score / self.total_questions)
    @property
    def feedback(self) -> str:
        pct = self.percentage
        if pct >= 80:
            return "Excellent. You have a strong grasp of this topic."
        if pct >= 60:
            return "Good work. A few areas still need attention."
        if pct >= 40:
            return "Fair. Review the explanations below and try again."
        return "Needs work. Revisit the basics, then retake the quiz."