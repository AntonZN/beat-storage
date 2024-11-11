import datetime
import jwt
from loguru import logger


def generate_access_token(employee):
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=1000)

    access_token_payload = {
        "username": employee.username,
        "exp": exp,
        "iat": datetime.datetime.utcnow(),
    }
    private_key = open("sm.key").read()
    access_token = jwt.encode(access_token_payload, private_key, algorithm="RS256")

    return access_token


def validate_access_token(token):
    try:
        public_key = open("sm.key.pub").read()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_signature": True, "verify_exp": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("Token Validation Error: ExpiredSignatureError")
    except Exception as e:
        logger.error(f"Token Validation Error: {e}")
