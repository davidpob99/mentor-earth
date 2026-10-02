from django import forms
from django.conf import settings

from accounts.models import CareerStage

from .models import MentorProfile, MentoringRelationship


class MentorForm(forms.ModelForm):
    class Meta:
        model = MentorProfile
        fields = ["capacity", "contact_preference", "slack_handle", "superpower", "superpower_other"]
        labels = {
            "capacity": "How many mentees would you like?",
            "contact_preference": "How should your mentees contact you?",
            "slack_handle": "Slack handle",
            "superpower": "What's your research superpower?",
            "superpower_other": "Your own superpower",
        }
        widgets = {
            "contact_preference": forms.RadioSelect,
            "superpower": forms.RadioSelect,
            "slack_handle": forms.TextInput(attrs={"placeholder": "@you"}),
            "superpower_other": forms.TextInput(attrs={"placeholder": "e.g. Asking silly questions"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["capacity"] = forms.TypedChoiceField(
            label=self.fields["capacity"].label,
            choices=[(n, str(n)) for n in range(1, settings.MAX_MENTEES_PER_MENTOR + 1)],
            coerce=int,
            widget=forms.RadioSelect,
            initial=self.instance.capacity if self.instance.pk else 1,
        )
        for name in ("contact_preference", "superpower"):
            self.fields[name].choices = [c for c in self.fields[name].choices if c[0]]

    def clean(self):
        data = super().clean()
        needs_slack = data.get("contact_preference") in (
            MentorProfile.Contact.SLACK,
            MentorProfile.Contact.EITHER,
        )
        if needs_slack and not data.get("slack_handle", "").strip():
            self.add_error("slack_handle", "Add your Slack handle so mentees can find you.")
        if data.get("superpower") == MentorProfile.Superpower.OTHER and not data.get(
            "superpower_other", ""
        ).strip():
            self.add_error("superpower_other", "Tell us your superpower ✨")
        return data


class MentorFilterForm(forms.Form):
    research = forms.CharField(
        required=False,
        label="Research area",
        widget=forms.TextInput(attrs={"placeholder": "Any"}),
    )
    stage = forms.ChoiceField(
        required=False, label="Career stage", choices=[("", "Any")] + CareerStage.choices
    )


class EndReasonForm(forms.Form):
    reason = forms.ChoiceField(
        required=False,
        label="Why? (optional)",
        choices=[("", "Prefer not to say")] + MentoringRelationship.EndReason.choices,
    )
