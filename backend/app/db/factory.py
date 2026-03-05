"""Database client factory for multi-cloud support."""
from typing import Optional
from ..config import get_settings
from .interface import DatabaseInterface


def create_db_client(table_name: Optional[str] = None) -> DatabaseInterface:
    """
    Create and return the appropriate database client based on cloud provider setting.

    Args:
        table_name: Optional database/table name override

    Returns:
        Database client instance implementing DatabaseInterface

    Raises:
        ValueError: If cloud_provider is not supported
    """
    settings = get_settings()
    cloud_provider = settings.cloud_provider.lower()

    if cloud_provider == "aws":
        from .dynamodb import DynamoDBClient
        return DynamoDBClient(table_name=table_name)
    elif cloud_provider == "gcp":
        # Will be implemented in Phase 3
        from .firestore import FirestoreClient
        return FirestoreClient(database=table_name)
    else:
        raise ValueError(
            f"Unsupported cloud provider: {cloud_provider}. "
            f"Supported providers: 'aws', 'gcp'"
        )


# For backwards compatibility, keep get_db_client as alias
get_db_client = create_db_client
