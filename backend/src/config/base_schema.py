from pydantic import BaseModel as _BaseModel
from django.core.serializers import serialize


class BaseModel(_BaseModel):
    @classmethod
    async def _from_orm(cls, instances):
        return [cls.from_orm(inst) async for inst in instances]

    @classmethod
    async def _from_list(cls, instances):
        return [inst async for inst in instances]

    @classmethod
    async def from_qs(cls, qs):
        return await cls._from_orm(qs)

    @classmethod
    async def from_values(cls, qs):
        return await cls._from_list(qs)

    @classmethod
    def _model_to_dict(cls, instance):
        data = serialize("python", [instance])[0]
        return dict(id=data["pk"], **data["fields"])

    @classmethod
    def from_orm_and_related(cls, instance, related_field_name):
        data = cls._model_to_dict(instance)
        related_instance = getattr(instance, related_field_name)
        data[related_field_name] = [
            cls._model_to_dict(field) for field in related_instance.all()
        ]
        return data

    @classmethod
    def from_orm_and_related_list(cls, instance, related_fields):
        data = cls._model_to_dict(instance)
        for field in related_fields:
            related_instance = getattr(instance, field)
            data[field] = [
                cls._model_to_dict(field) for field in related_instance.all()
            ]
        return data

    class Config:
        populate_by_name = True
        from_attributes = True
