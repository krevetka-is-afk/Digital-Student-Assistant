from django.contrib import admin

from .models import EmailVerificationCode, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "role", "email_verified_at", "created_at", "updated_at")
    list_filter = ("role", "email_verified_at", "created_at")
    search_fields = ("user__username", "user__email")


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
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
