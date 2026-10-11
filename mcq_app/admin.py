from django.contrib import admin
from .models import QuizAttempt, Semester, Subject, Topic

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "description")

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "semester", "description")
    list_filter = ("semester",)
    search_fields = ("name",)

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "subject")
    list_filter = ("subject__semester", "subject")
    search_fields = ("name",)

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "topic", "score", "total_questions", "completed_at")
    list_filter = ("topic__subject",)
    search_fields = ("user__username", "topic__name")
    date_hierarchy = "completed_at"
    readonly_fields = ("user", "topic", "score", "total_questions", "completed_at")
    def has_add_permission(self, request):
        return False