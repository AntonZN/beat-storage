from typing import List, Optional, Literal

from django.db.models import Prefetch, F
from fastapi import APIRouter, status, Query, HTTPException, Depends
from fastapi_pagination import Page
from fastapi_pagination.paginator import paginate

from src.domain.beats.models import Beat, Tag, Category
from src.domain.beats.schemas import BeatSchema, TagSchema, CategorySchema

router = APIRouter()


def parse_category_ids(
    category_ids: Optional[str] = Query(
        None,
        description="Список id категорий через запятую. Пример: `1,2,3`",
    )
) -> Optional[List[int]]:
    if category_ids:
        try:
            return [int(cat_id) for cat_id in category_ids.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="category_ids должны содержать только числа, разделенные запятыми",
            )
    return None


def parse_tag_ids(
    tag_ids: Optional[str] = Query(
        None,
        description="Список id тегов через запятую. Пример: `5,6`",
    )
) -> Optional[List[int]]:
    if tag_ids:
        try:
            return [int(tag_id) for tag_id in tag_ids.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="tag_ids должны содержать только числа, разделенные запятыми",
            )
    return None


def get_queryset_beats(tag_ids=None, category_ids=None, is_paid=None, order_by=None):
    """
    Формирует queryset для выборки битов с фильтрацией и сортировкой.
    """
    queryset = Beat.objects.filter(is_hidden=False).prefetch_related(
        Prefetch("categories", queryset=Category.objects.all()),
        Prefetch("tags", queryset=Tag.objects.all()),
    )

    if category_ids:
        queryset = queryset.filter(categories__id__in=category_ids)

    if tag_ids:
        queryset = queryset.filter(tags__id__in=tag_ids)

    if is_paid is not None:
        queryset = queryset.filter(is_paid=is_paid)

    ordering_map = {
        "default": "order",
        "created": "-created_at",
        "likes": "-likes_count",
        "usages": "-usage_count",
    }

    return queryset.order_by(ordering_map.get(order_by, "order"))


@router.get(
    "/tags/",
    response_model=List[TagSchema],
    status_code=status.HTTP_200_OK,
    name="Список тегов",
    description="Возвращает список всех доступных тегов.",
)
async def get_all_tags():
    return await TagSchema.from_qs(Tag.objects.all())


@router.get(
    "/categories/",
    response_model=List[CategorySchema],
    status_code=status.HTTP_200_OK,
    name="Список категорий",
    description="Возвращает список всех категорий.",
)
async def get_all_categories():
    return await CategorySchema.from_qs(Category.objects.all())


@router.get(
    "/beats",
    response_model=Page[BeatSchema],
    status_code=status.HTTP_200_OK,
    name="Список битов",
    description="Метод возвращает список битов с возможностью фильтрации и сортировки. "
    "Этот метод использует пагинацию для инфинити скрола в приложении.",
    responses={
        200: {"description": "Успешное получение списка битов"},
        400: {"description": "Некорректные параметры запроса"},
    },
)
async def get_beats(
    category_ids: Optional[List[int]] = Depends(parse_category_ids),
    tag_ids: Optional[List[int]] = Depends(parse_tag_ids),
    is_paid: Optional[bool] = Query(
        False, description="Фильтр по платным/бесплатным битам. По умолчанию: `False`"
    ),
    order_by: Literal["default", "created", "likes", "usages"] = Query(
        "default",
        description=(
            "Сортировка битов:\n"
            "- `default`: стандартная сортировка\n"
            "- `created`: сначала новые\n"
            "- `likes`: по количеству лайков\n"
            "- `usages`: по количеству использований"
        ),
    ),
):
    beats_queryset = get_queryset_beats(tag_ids, category_ids, is_paid, order_by)
    beats = []

    async for beat in beats_queryset:
        beats.append(BeatSchema.from_orm_and_related_list(beat, ["tags", "categories"]))

    return paginate(beats)


@router.patch(
    "/beats/{beat_id}/event/usage",
    status_code=status.HTTP_200_OK,
    name="Событие - Бит использован",
    description="Увеличивает счетчик использований для выбранного бита.",
    responses={
        200: {"description": "Счетчик использований успешно увеличен"},
        404: {"description": "Бит не найден"},
    },
)
async def beat_usage(beat_id: int):
    await Beat.objects.filter(id=beat_id).aupdate(usage_count=F("usage_count") + 1)


@router.patch(
    "/beats/{beat_id}/event/like",
    status_code=status.HTTP_200_OK,
    name="Событие - Поставить лайк",
    description="Увеличивает счетчик лайков для выбранного бита.",
    responses={
        200: {"description": "Счетчик лайков успешно увеличен"},
        404: {"description": "Бит не найден"},
    },
)
async def beat_like(beat_id: int):
    await Beat.objects.filter(id=beat_id).aupdate(likes_count=F("likes_count") + 1)
