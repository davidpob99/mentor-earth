from django.urls import path

from . import views

app_name = "mentoring"

urlpatterns = [
    path("", views.home, name="home"),
    path("mentors/", views.mentor_list, name="mentor_list"),
    path("mentors/<int:pk>/", views.mentor_detail, name="mentor_detail"),
    path("mentors/<int:pk>/choose/", views.choose_mentor, name="choose_mentor"),
    path("mentor/join/", views.mentor_join, name="mentor_join"),
    path("mentor/pause/", views.pause_mentoring, name="pause_mentoring"),
    path("mentor/resume/", views.resume_mentoring, name="resume_mentoring"),
    path("mentor/stop/", views.stop_mentoring, name="stop_mentoring"),
    path("profile/", views.profile, name="profile"),
    path("relationships/<int:pk>/end/", views.end_relationship, name="end_relationship"),
    path("leave/", views.leave_program, name="leave_program"),
    path("notifications/", views.notifications, name="notifications"),
    path("history/", views.history, name="history"),
    path("staff/", views.staff_dashboard, name="staff_dashboard"),
]
