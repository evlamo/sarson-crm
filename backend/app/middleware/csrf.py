"""CSRF protection middleware."""

import secrets
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF token validation middleware."""
    
    CSRF_TOKEN_LENGTH = 32
    CSRF_HEADER = "X-CSRF-Token"
    CSRF_COOKIE = "csrf_token"
    
    # Methods that require CSRF token validation
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Validate CSRF token for state-changing requests."""
        
        # Generate CSRF token for all requests
        request.scope["csrf_token"] = self._get_or_create_token(request)
        
        # Validate token for state-changing requests
        if request.method not in self.SAFE_METHODS:
            # Skip validation for public endpoints
            if request.url.path.startswith("/api/v1/auth/register") or \
               request.url.path.startswith("/api/v1/auth/login") or \
               request.url.path.startswith("/api/v1/auth/refresh") or \
               request.url.path.startswith("/api/v1/auth/forgot-password") or \
               request.url.path.startswith("/api/v1/auth/reset-password") or \
               request.url.path.startswith("/api/v1/auth/verify-email") or \
               request.url.path.startswith("/health") or \
               request.url.path.startswith("/docs") or \
               request.url.path.startswith("/redoc"):
                # Skip CSRF validation for public endpoints
                response = await call_next(request)
                return response
            
            # Validate CSRF token for protected endpoints
            token_from_header = request.headers.get(self.CSRF_HEADER, "")
            token_from_cookie = request.cookies.get(self.CSRF_COOKIE, "")
            
            if not token_from_header or token_from_header != token_from_cookie:
                return Response("CSRF token validation failed", status_code=403)
        
        response = await call_next(request)
        
        # Set CSRF token in response cookie
        csrf_token = self._get_or_create_token(request)
        response.set_cookie(
            self.CSRF_COOKIE,
            csrf_token,
            max_age=3600,  # 1 hour
            httponly=False,  # Must be accessible to JavaScript
            secure=False,  # Allow HTTP in development
            samesite="lax"
        )
        
        # Add CSRF token to response headers
        response.headers[self.CSRF_HEADER] = csrf_token
        
        return response
    
    def _get_or_create_token(self, request: Request) -> str:
        """Get existing CSRF token from cookie or create new one."""
        existing_token = request.cookies.get(self.CSRF_COOKIE, "")
        if existing_token and len(existing_token) == self.CSRF_TOKEN_LENGTH:
            return existing_token
        return secrets.token_urlsafe(self.CSRF_TOKEN_LENGTH)
