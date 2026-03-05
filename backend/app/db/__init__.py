"""Database modules."""
from .interface import DatabaseInterface
from .factory import create_db_client, get_db_client
from .dynamodb import DynamoDBClient

__all__ = [
    "DatabaseInterface",
    "create_db_client",
    "get_db_client",
    "DynamoDBClient",  # Kept for backwards compatibility
]
