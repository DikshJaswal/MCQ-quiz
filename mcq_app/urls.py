from django.urls import path
from . import views

app_name = "mcq_app"
urlpatterns = [
    path("", views.home, name="home"),
    path("semester/<int:semester_id>/", views.semester_subjects, name="semester_subjects"),
    path("semester/<int:semester_id>/subject/<int:subject_id>/", views.subject_topics, name="subject_topics"),
    path("topic/<int:topic_id>/", views.quiz_intro, name="quiz_intro"),
    path("topic/<int:topic_id>/quiz/", views.quiz_take, name="quiz_take"),
    path("attempt/<int:attempt_id>/", views.quiz_results, name="quiz_results"),
]