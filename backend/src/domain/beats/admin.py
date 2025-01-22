from django.contrib import admin
from ordered_model.admin import OrderedModelAdmin

from .models import Beat, Category, Tag


@admin.register(Category)
class CategoryAdmin(OrderedModelAdmin):
    list_display = ("name", "is_hidden", "move_up_down_links")
    list_filter = ("is_hidden",)
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(OrderedModelAdmin):
    list_display = ("name", "move_up_down_links")
    search_fields = ("name",)


@admin.register(Beat)
class BeatAdmin(OrderedModelAdmin):
    list_display = (
        "name",
        "is_paid",
        "is_hidden",
        "usage_count",
        "likes_count",
        "created_at",
        "move_up_down_links",
    )
    search_fields = ("name",)
    list_filter = ("is_paid", "is_hidden", "categories", "tags")
    filter_horizontal = ("categories", "tags")
    readonly_fields = ("usage_count", "likes_count", "created_at")
    autocomplete_fields = ("categories", "tags")
    fields = (
        "name",
        "tags",
        "categories",
        "is_hidden",
        "is_paid",
        "description",
        "file",
        "preview",
        "image",
        "usage_count",
        "likes_count",
        "created_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("tags")
