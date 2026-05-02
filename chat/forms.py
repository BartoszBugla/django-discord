from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile, Channel, Message


class UserReportForm(forms.Form):
    reason = forms.CharField(
        label="Powód zgłoszenia",
        min_length=10,
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Opisz, dlaczego zgłaszasz tego użytkownika (minimum 10 znaków)…",
            }
        ),
    )


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="Adres e-mail",
        widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        labels = {
            "username": "Nazwa użytkownika",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.setdefault("class", "form-control")
        self.fields["username"].widget.attrs.setdefault("autocomplete", "username")
        self.fields["password1"].label = "Hasło"
        self.fields["password2"].label = "Powtórz hasło"
        self.fields["password1"].widget.attrs.setdefault("class", "form-control")
        self.fields["password2"].widget.attrs.setdefault("class", "form-control")
        self.fields["password1"].widget.attrs.setdefault("autocomplete", "new-password")
        self.fields["password2"].widget.attrs.setdefault("autocomplete", "new-password")
        self.fields["password1"].help_text = (
            "Minimum 8 znaków. Hasło nie może być zbyt podobne do nazwy użytkownika ani być powszechnie używane."
        )
        self.fields["password2"].help_text = "Wpisz ponownie to samo hasło w celu weryfikacji."

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Podaj adres e-mail.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ten adres e-mail jest już zarejestrowany.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar", "opis"]
        labels = {
            "avatar": "Awatar",
            "opis": "Opis profilu",
        }
        widgets = {
            "opis": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Krótko o sobie…"}
            ),
            "avatar": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }


class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel
        fields = ["nazwa", "opis"]
        labels = {
            "nazwa": "Nazwa kanału",
            "opis": "Opis",
        }
        widgets = {
            "nazwa": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "np. ogólny",
                    "autocomplete": "off",
                }
            ),
            "opis": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "O czym jest ten kanał?",
                }
            ),
        }


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["tresc", "obrazek", "audio"]
        labels = {
            "tresc": "Treść",
            "obrazek": "Obraz",
            "audio": "Nagranie audio",
        }
        widgets = {
            "tresc": forms.TextInput(
                attrs={
                    "placeholder": "Napisz wiadomość…",
                    "autocomplete": "off",
                    "class": "form-control",
                }
            ),
            "obrazek": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "audio": forms.FileInput(attrs={"class": "form-control", "accept": "audio/*"}),
        }

    def clean(self):
        cleaned = super().clean()
        tresc = (cleaned.get("tresc") or "").strip()
        has_media = bool(cleaned.get("obrazek")) or bool(cleaned.get("audio"))
        if not tresc and not has_media:
            raise forms.ValidationError(
                {"tresc": "Wiadomość nie może być pusta (dodaj tekst, obraz lub plik audio)."},
                code="empty_message",
            )
        cleaned["tresc"] = tresc
        return cleaned
