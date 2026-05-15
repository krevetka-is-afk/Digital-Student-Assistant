import re

from apps.projects.normalization import normalize_technology_tags
from apps.projects.transitions import MODERATION_COMMENT_MIN_LEN
from django import forms

_DESCRIPTION_MAX = 2000
_TAGS_MAX = 20
_TAG_ITEM_MAX = 50

TAG_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9 \-\.+#_]*$")


def _validate_tags(tags: list[str]) -> list[str]:
    if len(tags) > _TAGS_MAX:
        raise forms.ValidationError(f"Максимум {_TAGS_MAX} тегов.")
    invalid = [t for t in tags if len(t) > _TAG_ITEM_MAX or not TAG_RE.match(t)]
    if invalid:
        raise forms.ValidationError(
            "Недопустимые теги: %(tags)s. "
            "Используйте буквы, цифры, дефис, точку, +, #. "
            f"Максимум {_TAG_ITEM_MAX} символов на тег.",
            params={"tags": ", ".join(invalid)},
        )
    return tags


_IS_PAID_CHOICES = [("", "Не указано"), ("yes", "Да"), ("no", "Нет")]


class ProjectFrontendForm(forms.Form):
    title = forms.CharField(
        max_length=255,
        error_messages={
            "required": "Название обязательно.",
            "max_length": "Не более 255 символов.",
        },
    )
    description = forms.CharField(
        widget=forms.Textarea,
        required=False,
        max_length=_DESCRIPTION_MAX,
        error_messages={"max_length": f"Описание не может превышать {_DESCRIPTION_MAX} символов."},
    )
    tech_tags_raw = forms.CharField(required=False)
    team_size = forms.IntegerField(
        min_value=1,
        max_value=100,
        error_messages={
            "required": "Укажите размер команды.",
            "invalid": "Введите целое число.",
            "min_value": "Минимум 1 участник.",
            "max_value": "Максимум 100 участников.",
        },
    )
    work_format = forms.CharField(
        required=False,
        max_length=255,
        error_messages={"max_length": "Не более 255 символов."},
    )
    hours_per_week = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=168,
        decimal_places=2,
        max_digits=8,
        error_messages={
            "invalid": "Введите число.",
            "min_value": "Не может быть отрицательным.",
            "max_value": "Максимум 168 часов.",
        },
    )
    is_paid = forms.ChoiceField(
        required=False,
        choices=_IS_PAID_CHOICES,
    )
    application_deadline = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        error_messages={"invalid": "Введите дату в формате ДД.ММ.ГГГГ."},
    )
    selection_criteria = forms.CharField(
        required=False,
        widget=forms.Textarea,
        max_length=_DESCRIPTION_MAX,
        error_messages={"max_length": f"Не более {_DESCRIPTION_MAX} символов."},
    )
    supervisor_name = forms.CharField(
        required=False,
        max_length=255,
        error_messages={"max_length": "Не более 255 символов."},
    )
    supervisor_email = forms.EmailField(
        required=False,
        max_length=255,
        error_messages={
            "invalid": "Введите корректный email.",
            "max_length": "Не более 255 символов.",
        },
    )
    supervisor_department = forms.CharField(
        required=False,
        max_length=255,
        error_messages={"max_length": "Не более 255 символов."},
    )

    def clean_tech_tags_raw(self):
        raw = self.cleaned_data.get("tech_tags_raw", "")
        if not raw.strip():
            return []
        return _validate_tags(normalize_technology_tags(raw.split(",")))

    def clean_is_paid(self):
        val = self.cleaned_data.get("is_paid", "")
        if val == "yes":
            return True
        if val == "no":
            return False
        return None


class ModerationProjectFieldsForm(forms.Form):
    study_course = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=6,
        error_messages={
            "min_value": "Курс от 1 до 6.",
            "max_value": "Курс от 1 до 6.",
            "invalid": "Введите число.",
        },
    )
    education_program = forms.CharField(required=False, max_length=255)
    credits = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=8,
        decimal_places=2,
        error_messages={"invalid": "Введите число.", "min_value": "Не может быть отрицательным."},
    )
    activity_type = forms.CharField(required=False, max_length=255)
    control_form = forms.CharField(required=False, max_length=255)
    results_presentation_format = forms.CharField(
        required=False, widget=forms.Textarea, max_length=2000
    )
    grading_formula = forms.CharField(required=False, widget=forms.Textarea, max_length=2000)
    student_participation_format = forms.CharField(required=False, max_length=255)


class InitiativeProjectForm(forms.Form):
    title = forms.CharField(
        max_length=255,
        error_messages={
            "required": "Название обязательно.",
            "max_length": "Не более 255 символов.",
        },
    )
    description = forms.CharField(
        widget=forms.Textarea,
        max_length=_DESCRIPTION_MAX,
        error_messages={
            "required": "Опишите проект — это главное поле.",
            "max_length": f"Описание не может превышать {_DESCRIPTION_MAX} символов.",
        },
    )
    tech_tags_raw = forms.CharField(required=False, label="Технологии")
    team_size = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=1,
        error_messages={
            "required": "Укажите размер команды.",
            "invalid": "Введите целое число.",
            "min_value": "Минимум 1 участник.",
            "max_value": "Максимум 10 участников.",
        },
    )
    supervisor_name = forms.CharField(
        max_length=255,
        required=False,
        label="Желаемый руководитель",
    )
    supervisor_personal_data_consent = forms.BooleanField(
        required=False,
        label="Согласие на обработку ПДн руководителя",
    )

    def clean(self) -> dict:
        cleaned_data = super().clean()
        supervisor_name = cleaned_data.get("supervisor_name", "").strip()
        supervisor_consent = bool(cleaned_data.get("supervisor_personal_data_consent"))
        if supervisor_name and not supervisor_consent:
            self.add_error(
                "supervisor_personal_data_consent",
                "Необходимо подтвердить согласие на предоставление данных руководителя.",
            )
        return cleaned_data

    def clean_tech_tags_raw(self):
        raw = self.cleaned_data.get("tech_tags_raw", "")
        if not raw.strip():
            return []
        return _validate_tags(normalize_technology_tags(raw.split(",")))


_INITIATIVE_MODERATION_COMMENT_MIN_LEN = 50


class InitiativeProposalModerationForm(forms.Form):
    DECISION_CHOICES = [
        ("approve", "Одобрить"),
        ("reject", "Отклонить"),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        error_messages={
            "required": "Укажите решение.",
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
        comment = cleaned_data.get("comment", "").strip()
        if decision == "reject":
            if not comment:
                self.add_error("comment", "При отклонении укажите причину.")
            elif len(comment) < _INITIATIVE_MODERATION_COMMENT_MIN_LEN:
                self.add_error(
                    "comment",
                    f"Причина отклонения слишком короткая — "
                    f"минимум {_INITIATIVE_MODERATION_COMMENT_MIN_LEN} символов.",
                )
        cleaned_data["comment"] = comment
        return cleaned_data


class ModerationDecisionForm(forms.Form):
    DECISION_CHOICES = [
        ("approve", "Одобрить"),
        ("reject", "Отклонить"),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        error_messages={
            "required": "Укажите решение.",
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
        comment = cleaned_data.get("comment", "").strip()
        if decision == "reject":
            if not comment:
                self.add_error("comment", "При отклонении укажите причину.")
            elif len(comment) < MODERATION_COMMENT_MIN_LEN:
                self.add_error(
                    "comment",
                    f"Причина отклонения слишком короткая — "
                    f"минимум {MODERATION_COMMENT_MIN_LEN} символов.",
                )
        cleaned_data["comment"] = comment
        return cleaned_data
