from django import forms
from django.contrib.auth.forms import AuthenticationForm

INPUT_CLASS = (
    "block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm "
    "focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
)


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={"autofocus": True, "autocomplete": "email", "class": INPUT_CLASS}
        ),
    )
    password = forms.CharField(
        label="Kata sandi",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "class": INPUT_CLASS}
        ),
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
