"""Middleware for the AGI Prompt System API."""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from ..i18n import get_translator, DEFAULT_LANGUAGE

class LocalizationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle request localization."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.default_language = DEFAULT_LANGUAGE
        self.supported_languages = ["en", "fr", "es", "de", "zh"]
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ):
        # Get language from Accept-Language header
        accept_language = request.headers.get("Accept-Language", self.default_language)
        
        # Parse the Accept-Language header to get the preferred language
        lang = self._parse_accept_language(accept_language)
        
        # Set the language in the request state
        request.state.language = lang
        
        try:
            # Process the request
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Translate error messages for HTTP exceptions
            translator = get_translator(lang)
            detail = e.detail
            
            if isinstance(detail, str):
                detail = translator.gettext(detail)
            elif isinstance(detail, dict):
                detail = {k: translator.gettext(v) if isinstance(v, str) else v 
                         for k, v in detail.items()}
            
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": detail, "code": e.status_code}
            )
        
        except Exception as e:
            # Handle unexpected errors
            translator = get_translator(lang)
            return JSONResponse(
                status_code=500,
                content={
                    "detail": translator.gettext("An unexpected error occurred"),
                    "code": 500
                }
            )
    
    def _parse_accept_language(self, accept_language: str) -> str:
        """Parse the Accept-Language header and return the best match.
        
        Args:
            accept_language: The value of the Accept-Language header
            
        Returns:
            The best matching language code from supported languages
        """
        if not accept_language:
            return self.default_language
        
        # Parse the Accept-Language header
        languages = []
        for lang in accept_language.split(","):
            try:
                if ";" in lang:
                    lang, q = lang.split(";")
                    q = float(q.strip("q="))
                else:
                    q = 1.0
                lang = lang.strip().lower()
                if "-" in lang:
                    lang = lang.split("-")[0]
                languages.append((lang, q))
            except (ValueError, IndexError):
                continue
        
        # Sort by quality
        languages.sort(key=lambda x: x[1], reverse=True)
        
        # Find the best match
        for lang, _ in languages:
            if lang in self.supported_languages:
                return lang
        
        return self.default_language


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        # Log request
        logger.info(
            "Request: %s %s",
            request.method,
            request.url.path,
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client": request.client.host if request.client else None,
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Log response
        logger.info(
            "Response: %s %s - %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "response_time": response.headers.get("X-Process-Time")
            }
        )
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                "img-src 'self' data:; "
                "font-src 'self' cdn.jsdelivr.net; "
                "connect-src 'self'"
            ),
            "Permissions-Policy": (
                "camera=(), microphone=(), geolocation=(), "
                "payment=()"
            ),
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        }
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        return response
