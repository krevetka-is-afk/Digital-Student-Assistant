from apps.account.models import DeadlineAudience
from apps.users.models import UserRole, normalize_email
from django import forms


class DeadlineForm(forms.Form):
    slug = forms.SlugField(
        max_length=80,
        error_messages={"required": "Введите slug (латиница, цифры, дефис)."},
    )
    title = forms.CharField(
        max_length=255,
        error_messages={"required": "Название обязательно."},
    )
    audience = forms.ChoiceField(choices=DeadlineAudience.choices)
    description = forms.CharField(widget=forms.Textarea, required=False)
    starts_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    ends_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    is_active = forms.BooleanField(required=False, initial=True)

class TemplateForm(forms.Form):
    slug = forms.SlugField(
        max_length=80,
        error_messages={"required": "Введите slug."},
    )
    title = forms.CharField(
        max_length=255,
        error_messages={"required": "Название обязательно."},
    )
    url = forms.URLField(
        error_messages={"required": "URL обязателен.", "invalid": "Введите корректный URL."},
    )
    audience = forms.ChoiceField(choices=DeadlineAudience.choices)
    description = forms.CharField(widget=forms.Textarea, required=False)
    is_active = forms.BooleanField(required=False, initial=True)

class ExternalAllowlistBulkForm(forms.Form):
    emails = forms.CharField(
        widget=forms.Textarea,
        error_messages={"required": "Specify at least one email."},
    )
    allowed_role = forms.ChoiceField(
        choices=[(UserRole.CUSTOMER, "Customer")],
        initial=UserRole.CUSTOMER,
    )
    note = forms.CharField(required=False, max_length=255)

    def clean_emails(self) -> list[str]:
        raw = self.cleaned_data["emails"]
        values = []
        seen: set[str] = set()
        for part in raw.replace(",", " ").replace(";", " ").split():
            email = normalize_email(part)
            if not email or email in seen:
                continue
            seen.add(email)
            values.append(email)
        if not values:
            raise forms.ValidationError("No valid emails found.")
        return values
