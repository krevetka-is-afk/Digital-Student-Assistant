import re

from apps.users.models import UserRole, normalize_email
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

_PASSWORD_MIN = 8
_NAME_MAX = 100

_VALIDATOR_MESSAGE_MAP: dict[str, str] = {
    "too short": f"Password is too short. Minimum length is {_PASSWORD_MIN} characters.",
    "too common": "Password is too common. Try another one.",
    "entirely numeric": "Password cannot contain only digits.",
    "too similar": "Password is too similar to the email or user name.",
}


def _translate_validator_message(msg: str) -> str:
    lower = msg.lower()
    for fragment, translation in _VALIDATOR_MESSAGE_MAP.items():
        if fragment in lower:
            return translation
    return msg


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
        error_messages={
            "required": "Enter email.",
            "invalid": "Enter a valid email address.",
        },
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        error_messages={"required": "Enter password."},
    )

    def clean_email(self) -> str:
        return normalize_email(self.cleaned_data["email"])


class RegisterForm(forms.Form):
    name = forms.CharField(
        max_length=_NAME_MAX,
        required=False,
        error_messages={"max_length": f"Name cannot exceed {_NAME_MAX} characters."},
    )
    email = forms.EmailField(
        error_messages={
            "required": "Enter email.",
            "invalid": "Enter a valid email address.",
        },
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        error_messages={"required": "Enter password."},
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        error_messages={"required": "Repeat password."},
    )
    role = forms.ChoiceField(
        choices=[
            (UserRole.STUDENT, "Student"),
            (UserRole.CUSTOMER, "Customer"),
        ],
        initial=UserRole.STUDENT,
    )
    personal_data_consent = forms.BooleanField(
        required=True,
        error_messages={
            "required": "Personal data consent is required for registration.",
        },
    )

    def clean_name(self) -> str:
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            return name
        if not re.search(r"[^\W\d_]", name, re.UNICODE):
            raise forms.ValidationError("Name must contain at least one letter.")
        if re.search(r"\d", name):
            raise forms.ValidationError("Name must not contain digits.")
        return name

    def clean_email(self) -> str:
        email = normalize_email(self.cleaned_data["email"])
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_password(self) -> str:
        password = self.cleaned_data.get("password", "")
        try:
            validate_password(password)
        except ValidationError as exc:
            messages = [_translate_validator_message(message) for message in exc.messages]
            raise forms.ValidationError(messages)
        return password

    def clean_role(self) -> str:
        role = self.cleaned_data.get("role", UserRole.STUDENT)
        if role not in {UserRole.STUDENT, UserRole.CUSTOMER}:
            return UserRole.STUDENT
        return role

    def clean(self) -> dict:
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")
        if password and password2 and password != password2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data
