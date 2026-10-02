from django.contrib import admin

from .models import MentorProfile, MentoringRelationship, Notification


@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "status", "occupancy", "contact_preference", "superpower_display"]
    list_filter = ["status", "contact_preference"]
    search_fields = ["user__email", "user__full_name"]
    autocomplete_fields = ["user"]

    @admin.display(description="Places")
    def occupancy(self, obj):
        return f"{obj.active_mentee_count} / {obj.capacity}"


@admin.register(MentoringRelationship)
class MentoringRelationshipAdmin(admin.ModelAdmin):
    list_display = ["mentor", "mentee", "status", "started_at", "ended_at", "ended_by", "end_reason"]
    list_filter = ["status", "end_reason"]
    search_fields = ["mentor__email", "mentor__full_name", "mentee__email", "mentee__full_name"]
    autocomplete_fields = ["mentor", "mentee", "ended_by"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "kind", "message", "created_at", "read_at"]
    list_filter = ["kind"]
    search_fields = ["recipient__email", "message"]
