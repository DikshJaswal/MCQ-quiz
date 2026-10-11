from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User

def _style(form, autocomplete=None):
    """Give every widget the shared ``input`` class and sensible autocomplete hints."""
    for name, field in form.fields.items():
        field.widget.attrs.setdefault("class", "input")
        if autocomplete and name in autocomplete:
            field.widget.attrs["autocomplete"] = autocomplete[name]

class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Username or password is wrong.",
        "inactive": "This account is inactive.",
    }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"autofocus": True})
        _style(self, {"username": "username", "password": "current-password"})

class EmailNormalisingMixin:
    """Store emails lower-cased and reject case-insensitive duplicates."""
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        clash = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class SignupForm(EmailNormalisingMixin, UserCreationForm):
    email = forms.EmailField()
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"autofocus": True})
        _style(
            self,
            {
                "username": "username",
                "email": "email",
                "password1": "new-password",
                "password2": "new-password",
            },
        )


class ProfileForm(EmailNormalisingMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, {"username": "username", "email": "email",
                      "first_name": "given-name", "last_name": "family-name"})