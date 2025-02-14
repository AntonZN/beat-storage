from datetime import datetime
from typing import List, Optional, Any, TypeAlias, Union

from django.db.models.fields.files import ImageFieldFile, FieldFile
from django.conf import settings
from pydantic import Field, field_validator

from src.config.base_schema import BaseModel

File: TypeAlias = Union[Any]


class CategorySchema(BaseModel):
    id: int
    name: str
    is_hidden: bool = Field(alias="isHidden")


class TagSchema(BaseModel):
    id: int
    name: str


class BeatSchema(BaseModel):
    id: int
    name: str
    categories: List[CategorySchema]
    tags: List[TagSchema]
    is_paid: bool = Field(alias="isPaid")
    usage_count: int = Field(alias="usageCount")
    likes_count: int = Field(alias="likesCount")
    file: File
    preview: File
    image: File
    description: Optional[str]
    created_at: datetime

    @field_validator("file", mode="before")
    def get_file_url(cls, v):
        if not v:
            return None
        if v and type(v) is FieldFile:
            return v.url
        else:
            return f"{settings.AWS_FULL_BASE_URL}/{v}"

    @field_validator("preview", mode="before")
    def get_preview_url(cls, v):
        if not v:
            return None
        if v and type(v) is FieldFile:
            return v.url
        else:
            return f"{settings.AWS_FULL_BASE_URL}/{v}"

    @field_validator("image", mode="before")
    def get_image_url(cls, v):
        if not v:
            return None
        if v and type(v) is ImageFieldFile:
            return v.url
        else:
            return f"{settings.AWS_FULL_BASE_URL}/{v}"
