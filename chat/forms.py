from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile, Channel, Message


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Podaj adres email.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ten adres email jest juz zarejestrowany.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar", "opis"]


class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel
        fields = ["nazwa", "opis"]


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["tresc", "obrazek", "audio"]
        widgets = {
            "tresc": forms.TextInput(
                attrs={
                    "placeholder": "Napisz wiadomosc...",
                    "autocomplete": "off",
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()
        tresc = (cleaned.get("tresc") or "").strip()
        has_media = bool(cleaned.get("obrazek")) or bool(cleaned.get("audio"))
        if not tresc and not has_media:
            raise forms.ValidationError(
                {"tresc": "Wiadomosc nie moze byc pusta."},
                code="empty_message",
            )
        cleaned["tresc"] = tresc
        return cleaned
