from django.conf import settings
from fastapi import HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyQuery
from starlette import status

from src.app.authentication.secure import validate_access_token
from src.domain.employees.models import Employee

auth_scheme = HTTPBearer()

token_query = APIKeyQuery(name="token")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"Authorization": "Bearer"},
)


def token_validation(token: str = Security(token_query)) -> bool:
    if not token or token != settings.API_AUTH_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return True


async def get_current_employee(
    token: HTTPAuthorizationCredentials = Depends(auth_scheme),
):
    access_token = token.credentials
    payload = validate_access_token(access_token)

    try:
        username = payload.get("username")
        if username and await Employee.objects.filter(username=username).aexists():
            return await Employee.objects.filter(username=username).afirst()
        raise credentials_exception
    except Exception:
        raise credentials_exception
