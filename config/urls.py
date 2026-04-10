from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import include, path

from .views import TableauDeBordView

admin.site.site_header = "Administration Pharmexam"
admin.site.site_title = "Pharmexam Admin"
admin.site.index_title = "Gestion technique"


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "",
        login_required(TableauDeBordView.as_view()),
        name="dashboard",
    ),

    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    path("", include("academics.urls")),

    path("", include("exams.urls")),

    path("", include("rooms.urls")),

    path("", include("reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
