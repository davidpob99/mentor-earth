from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_request, name="login"),
    path("login/verify/", views.login_verify, name="verify"),
    path("logout/", views.logout_view, name="logout"),
    path("welcome/", views.welcome, name="welcome"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
]
