from importlib import import_module

from apps.base.admin_unfold import UnfoldModelAdmin
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import (
    AdminPasswordChangeForm as DjangoAdminPasswordChangeForm,
)
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm
from django.contrib.auth.models import Group, User

from .models import EmailVerificationCode, UserProfile

try:  # pragma: no cover - exercised when django-unfold is installed in CI/deploy.
    unfold_forms = import_module("unfold.forms")
    AdminPasswordChangeForm = unfold_forms.AdminPasswordChangeForm
    UserChangeForm = unfold_forms.UserChangeForm
    UserCreationForm = unfold_forms.UserCreationForm
except ModuleNotFoundError:  # pragma: no cover - local offline fallback only.
    AdminPasswordChangeForm = DjangoAdminPasswordChangeForm
    UserChangeForm = DjangoUserChangeForm
    UserCreationForm = DjangoUserCreationForm


for auth_model in (User, Group):
    if auth_model in admin.site._registry:
        admin.site.unregister(auth_model)


@admin.register(User)
class UserAdmin(BaseUserAdmin, UnfoldModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, UnfoldModelAdmin):
    pass


@admin.register(UserProfile)
class UserProfileAdmin(UnfoldModelAdmin):
    list_display = ("id", "user", "role", "email_verified_at", "created_at", "updated_at")
    list_filter = ("role", "email_verified_at", "created_at")
    search_fields = ("user__username", "user__email")


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(UnfoldModelAdmin):
    list_display = (
        "id",
        "user",
        "email",
        "purpose",
        "attempt_count",
        "sent_at",
        "expires_at",
        "consumed_at",
    )
    list_filter = ("purpose", "sent_at", "expires_at", "consumed_at")
    search_fields = ("user__username", "user__email", "email")
    readonly_fields = ("code_hash", "sent_at", "consumed_at")
