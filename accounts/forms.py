from django import forms

from .models import User


class EmailForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "you@institution.org"})
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class CodeForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "pattern": "[0-9]{6}",
                "placeholder": "123456",
                "class": "code-input",
            }
        ),
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "research_topic", "career_stage", "photo"]
        labels = {
            "full_name": "Your name",
            "research_topic": "What do you work on?",
            "career_stage": "Career stage",
            "photo": "Profile picture (optional)",
        }
        widgets = {
            "career_stage": forms.RadioSelect,
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("full_name", "research_topic", "career_stage"):
            self.fields[name].required = True
        # Drop the empty "---------" choice from the radio list.
        self.fields["career_stage"].choices = [
            c for c in self.fields["career_stage"].choices if c[0]
        ]
