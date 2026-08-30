from qdrant_client.models import Filter, FieldCondition, MatchAny
from config import ROLE_COLLECTIONS, SQL_ROLES


def get_role_collections(role: str) -> list[str]:
    return ROLE_COLLECTIONS.get(role, [])


def is_sql_permitted(role: str) -> bool:
    return role in SQL_ROLES


def build_qdrant_filter(role: str) -> Filter:
    """Enforces RBAC at the Qdrant metadata-filter layer — before results reach the LLM."""
    return Filter(
        must=[
            FieldCondition(
                key="collection",
                match=MatchAny(any=get_role_collections(role)),
            )
        ]
    )


def format_rbac_denial(role: str) -> str:
    collections = get_role_collections(role)
    readable_role = role.replace("_", " ").title()
    return (
        f"As a {readable_role}, your access is limited to the following collections: "
        f"{', '.join(collections)}. "
        "The information you requested falls outside your permitted access scope. "
        "Please contact your administrator if you require broader access."
    )
