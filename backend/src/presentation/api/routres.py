from fastapi import APIRouter, Depends

from .endpoints.beats import router as beats_router

from src.app.authentication.deps import token_validation

api_router = APIRouter(prefix="/api/v1")

service_api_router = APIRouter(
    prefix="/api/v1", dependencies=[Depends(token_validation)]
)


api_routes = {
    "/": ["Апи", [beats_router]],
}


for prefix, (tag, routers) in api_routes.items():
    for router in routers:
        api_router.include_router(
            router, prefix=prefix, tags=[tag], dependencies=[Depends(token_validation)]
        )
