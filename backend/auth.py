import time
import jwt
from config import DEMO_USERS, ROLE_COLLECTIONS, SECRET_KEY


def authenticate(username: str, password: str) -> dict | None:
    user = DEMO_USERS.get(username)
    if not user or user["password"] != password:
        return None
    return user


def create_token(username: str, role: str) -> str:
    payload = {
        "username": username,
        "role": role,
        "exp": int(time.time()) + 86400,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def get_accessible_collections(role: str) -> list[str]:
    return ROLE_COLLECTIONS.get(role, [])
