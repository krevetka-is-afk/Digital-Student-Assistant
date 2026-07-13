from django.contrib import admin

from .models import Message, Thread


class MessageInline(admin.TabularInline):
    model = Message
    fields = ("sender", "body", "created_at")
    readonly_fields = ("sender", "created_at")
    extra = 0
    ordering = ("created_at",)


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ("subject", "participants_display", "messages_count", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("subject", "participants__username", "participants__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MessageInline]

    def participants_display(self, obj):
        return ", ".join(
            u.get_full_name() or u.username for u in obj.participants.all()
        )
    participants_display.short_description = "Участники"

    def messages_count(self, obj):
        return obj.messages.count()
    messages_count.short_description = "Сообщений"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "thread", "body_preview", "created_at", "read_count")
    list_filter = ("created_at",)
    search_fields = ("sender__username", "sender__email", "body", "thread__subject")
    readonly_fields = ("created_at",)
    raw_id_fields = ("thread", "sender")

    def body_preview(self, obj):
        return obj.body[:80] + "…" if len(obj.body) > 80 else obj.body
    body_preview.short_description = "Текст"

    def read_count(self, obj):
        return obj.read_by.count()
    read_count.short_description = "Прочитали"
