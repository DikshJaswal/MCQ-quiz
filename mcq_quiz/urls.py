from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("mcq_app.urls")),
]
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"