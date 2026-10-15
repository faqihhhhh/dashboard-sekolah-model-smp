from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm

from apps.core.forms import INPUT_CLASS, StyledFormMixin

from .models import User


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


class UserPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    """Perubahan kata sandi mandiri dengan validasi kata sandi Django."""

    old_password = forms.CharField(
        label="Kata sandi saat ini",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password1 = forms.CharField(
        label="Kata sandi baru",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="Ulangi kata sandi baru",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )


class UserCreateForm(StyledFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="Kata sandi",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label="Ulangi kata sandi",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["full_name", "email", "role"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email ini sudah terdaftar.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1, password2 = cleaned.get("password1"), cleaned.get("password2")
        if password1 and password2:
            if password1 != password2:
                self.add_error("password2", "Kedua kata sandi tidak sama.")
            else:
                candidate = User(
                    email=cleaned.get("email", ""), full_name=cleaned.get("full_name", "")
                )
                try:
                    password_validation.validate_password(password1, candidate)
                except forms.ValidationError as error:
                    self.add_error("password1", error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserUpdateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "email", "role", "is_active"]

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].disabled = True
        self.fields["email"].help_text = "Email tidak dapat diubah."
        # Mencegah Super Admin mengunci dirinya sendiri.
        if acting_user is not None and acting_user.pk == self.instance.pk:
            self.fields["role"].disabled = True
            self.fields["is_active"].disabled = True
            self.fields[
                "role"
            ].help_text = "Anda tidak dapat mengubah peran atau menonaktifkan akun Anda sendiri."


class AdminSetPasswordForm(StyledFormMixin, SetPasswordForm):
    """Super Admin mengatur ulang kata sandi pengguna."""
