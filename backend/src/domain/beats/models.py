import uuid

from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver

from ordered_model.models import OrderedModelQuerySet
from parler.managers import TranslatableQuerySet

from ordered_model.models import OrderedModel
from parler.managers import TranslatableManager


class TranslatableOrderedQuerySet(TranslatableQuerySet, OrderedModelQuerySet):
    pass


class TranslatableOrderedManager(TranslatableManager):
    _queryset_class = TranslatableOrderedQuerySet


class Category(OrderedModel):
    name = models.CharField(max_length=100, verbose_name="Название категории")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ("order",)

    def __str__(self):
        return self.name


class Tag(OrderedModel):
    name = models.CharField(max_length=100, verbose_name="Название")

    class Meta:
        verbose_name = "Тег"
        ordering = ("order",)
        verbose_name_plural = "Теги"

    def __str__(self):
        return self.name


class Beat(OrderedModel):
    def upload_to(self, filename):
        name = uuid.uuid4()
        ext = filename.split(".")[-1]
        return f"beats/{name}.{ext}"

    name = models.CharField(max_length=100, verbose_name="Название")
    categories = models.ManyToManyField(
        Category, related_name="beats", verbose_name="Категории"
    )
    tags = models.ManyToManyField(
        Tag,
        related_name="beats",
        verbose_name="Теги",
        blank=True,
    )
    is_hidden = models.BooleanField(default=False, verbose_name="Скрыть")
    is_paid = models.BooleanField(default=False, verbose_name="Платный/по подписке")
    usage_count = models.PositiveIntegerField(
        default=0, verbose_name="Счетчик использования", editable=False
    )
    likes_count = models.PositiveIntegerField(
        default=0, verbose_name="Количество лайков", editable=False
    )
    file = models.FileField(
        upload_to=upload_to, blank=True, null=True, verbose_name="Файл"
    )
    preview = models.FileField(
        upload_to=upload_to, blank=True, null=True, verbose_name="Превью"
    )
    image = models.ImageField(
        upload_to=upload_to, blank=True, null=True, verbose_name="Картинка"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Описание")

    created_at = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name="Дата создания"
    )

    class Meta:
        verbose_name = "Бит"
        ordering = ("order",)
        verbose_name_plural = "Биты"

    def __str__(self):
        return self.name

    def increment_usage_count(self):
        self.usage_count = F("usage_count") + 1
        self.save(update_fields=["usage_count"])

    def increment_likes_count(self):
        self.likes_count = F("likes_count") + 1
        self.save(update_fields=["likes_count"])

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)


@receiver(post_delete, sender=Beat)
def delete_file_on_model_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)

    if instance.preview:
        instance.preview.delete(save=False)

    if instance.image:
        instance.image.delete(save=False)
