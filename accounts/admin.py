from django.contrib import admin

from .models import LoginCode, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Adding a user here invites them: they can then sign in with an email code."""

    list_display = ["email", "full_name", "research_topic", "career_stage", "is_active", "is_staff", "last_login"]
    list_filter = ["is_active", "is_staff", "career_stage"]
    search_fields = ["email", "full_name", "research_topic"]
    readonly_fields = ["last_login", "date_joined"]
    fieldsets = [
        (None, {"fields": ["email", "is_active"]}),
        ("Profile", {"fields": ["full_name", "research_topic", "career_stage", "photo"]}),
        ("Permissions", {"fields": ["is_staff", "is_superuser"]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]

    def save_model(self, request, obj, form, change):
        obj.email = obj.email.strip().lower()
        if not change:
            obj.set_unusable_password()
        super().save_model(request, obj, form, change)


@admin.register(LoginCode)
class LoginCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "expires_at", "attempts", "used_at"]
    readonly_fields = ["user", "code_hash", "created_at", "expires_at", "attempts", "used_at"]

    def has_add_permission(self, request):
        return False
