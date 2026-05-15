from apps.projects.normalization import normalize_technology_tags
from django import forms

from .projects import TAG_RE

_NAME_MAX = 100
_BIO_MIN = 10
_BIO_MAX = 500
_INTERESTS_MAX = 20
_INTEREST_ITEM_MIN = 2
_INTEREST_ITEM_MAX = 50


class ProfileEditForm(forms.Form):
    full_name = forms.CharField(required=False, max_length=_NAME_MAX)
    bio = forms.CharField(required=False, widget=forms.Textarea, max_length=_BIO_MAX)
    interests_raw = forms.CharField(required=False)

    def clean_bio(self):
        bio = self.cleaned_data.get("bio", "").strip()
        if bio and len(bio) < _BIO_MIN:
            raise forms.ValidationError(
                f"Слишком коротко — расскажите о себе хотя бы в {_BIO_MIN} символах."
            )
        return bio

    def clean_interests_raw(self):
        raw = self.cleaned_data.get("interests_raw", "")
        interests = normalize_technology_tags(raw.split(",")) if raw.strip() else []

        short = [t for t in interests if len(t) < _INTEREST_ITEM_MIN]
        long_ = [t for t in interests if len(t) > _INTEREST_ITEM_MAX]
        invalid = [t for t in interests if not TAG_RE.match(t)]

        if short:
            raise forms.ValidationError(
                f"Слишком короткий тег: «{short[0]}». Минимум {_INTEREST_ITEM_MIN} символа."
            )
        if long_:
            raise forms.ValidationError(
                f"Тег слишком длинный: «{long_[0][:20]}…». Максимум {_INTEREST_ITEM_MAX} символов."
            )
        if invalid:
            raise forms.ValidationError(
                f"Недопустимый тег: «{invalid[0]}». Используйте буквы, цифры, дефис, точку, +, #."
            )
        if len(interests) > _INTERESTS_MAX:
            raise forms.ValidationError(f"Максимум {_INTERESTS_MAX} интересов.")

        return interests
