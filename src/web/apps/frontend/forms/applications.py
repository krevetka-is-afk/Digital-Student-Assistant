
from apps.applications.models import ApplicationStatus
from apps.applications.transitions import REVIEW_COMMENT_MIN_LEN
from django import forms

_MOTIVATION_MIN = 30
_MOTIVATION_MAX = 3000

class MotivationForm(forms.Form):

    motivation = forms.CharField(
        required=False,
        max_length=_MOTIVATION_MAX,
        widget=forms.Textarea,
        error_messages={
            "max_length": "Мотивация слишком длинная.",
        },
    )

    def clean_motivation(self) -> str:
        motivation = self.cleaned_data.get("motivation", "").strip()
        if motivation and len(motivation) < _MOTIVATION_MIN:
            raise forms.ValidationError(
                f"Мотивация слишком короткая — опишите свой опыт и интерес "
                f"к проекту (минимум {_MOTIVATION_MIN} символов)."
            )
        return motivation

class ApplicationFilterForm(forms.Form):

    STATUS_CHOICES = [
        ("", "Все"),
        (ApplicationStatus.SUBMITTED, "На рассмотрении"),
        (ApplicationStatus.ACCEPTED,  "Принятые"),
        (ApplicationStatus.REJECTED,  "Отклонённые"),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
    )

    def clean_status(self) -> str:
        return self.cleaned_data.get("status", "")

class ReviewApplicationForm(forms.Form):

    DECISION_CHOICES = [
        ("accept", "Принять"),
        ("reject", "Отклонить"),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        error_messages={
            "required":       "Укажите решение.",
            "invalid_choice": "Недопустимое решение: %(value)s.",
        },
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea,
    )

    def clean(self) -> dict:
        cleaned_data = super().clean()
        decision = cleaned_data.get("decision")
        comment  = cleaned_data.get("comment", "").strip()
        if decision == "reject":
            if not comment:
                self.add_error("comment", "При отклонении укажите причину.")
            elif len(comment) < REVIEW_COMMENT_MIN_LEN:
                self.add_error(
                    "comment",
                    f"Причина отклонения слишком короткая — "
                    f"минимум {REVIEW_COMMENT_MIN_LEN} символов.",
                )
        cleaned_data["comment"] = comment
        return cleaned_data
