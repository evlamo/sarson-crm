from typing import TypeVar, Optional, Any, Dict, List

T = TypeVar("T")


def success_response(data: T, message: Optional[str] = None) -> Dict[str, Any]:
    """Construct a success response with data and optional message."""
    return {
        "data": data,
        "status": "success",
        "message": message,
    }


def error_response(message: str, status_code: int = 400) -> Dict[str, Any]:
    """Construct an error response."""
    return {
        "data": None,
        "status": "error",
        "message": message,
        "status_code": status_code,
    }


def paginated_response(
    items: List[T],
    total: int,
    page: int,
    per_page: int,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a paginated response with metadata."""
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    return {
        "data": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "status": "success",
        "message": message,
    }
