"""
FastAPI middleware for JWT authentication and shop scope injection.

This middleware:
1. Extracts JWT from Authorization header
2. Validates token using decode_token()
3. Injects shop_id and user_id into request.scope
4. Returns 401 for missing/invalid/expired tokens
5. Skips validation for public routes
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import jwt
import logging

from auth.jwt_utils import decode_token

logger = logging.getLogger(__name__)


# Public routes that don't require JWT authentication
PUBLIC_ROUTES = {
    "/",
    "/auth/signup",
    "/auth/login",
    "/api/verify-text",  # Public for MVP - merchants can test without account
    "/api/verify-image",  # Public for MVP
    "/api/verify-voice",  # Public for MVP
    "/api/search",  # Public scheme search
    "/api/connection-info",  # Setup/connection info for SMS integration
}


class ShopScopeMiddleware(BaseHTTPMiddleware):
    """
    JWT authentication middleware that extracts shop_id from token
    and injects it into request scope for merchant-scoped operations.
    
    Protected routes require a valid JWT in the Authorization header.
    Public routes (/, /auth/signup, /auth/login) bypass authentication.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """
        Process each request:
        - Check if route is public (skip auth)
        - Extract and validate JWT from Authorization header
        - Inject shop_id and user_id into request.scope
        - Return 401 for missing/invalid tokens on protected routes
        """
        path = request.url.path
        
        # Skip authentication for public routes
        if path in PUBLIC_ROUTES:
            return await call_next(request)
        
        # Also allow static files and favicon
        if path.startswith("/static/") or path.endswith(".ico"):
            return await call_next(request)
        
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            logger.warning(f"Missing Authorization header for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header required"}
            )
        
        # Check Bearer token format
        if not auth_header.startswith("Bearer "):
            logger.warning(f"Invalid Authorization header format for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Authorization header format. Use: Bearer <token>"}
            )
        
        # Extract token (remove "Bearer " prefix)
        token = auth_header[7:]  # len("Bearer ") == 7
        
        if not token:
            logger.warning(f"Empty token for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Token is empty"}
            )
        
        # Validate and decode token
        try:
            payload = decode_token(token)
            
            # Extract shop_id and user_id from token payload
            shop_id = payload.get("shop_id")
            user_id = payload.get("user_id")
            email = payload.get("email")
            
            if shop_id is None:
                logger.error(f"Token missing shop_id for {path}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid token: missing shop_id"}
                )
            
            # Inject shop_id and user_id into request scope
            # This makes them available to route handlers via request.scope
            request.scope["shop_id"] = shop_id
            request.scope["user_id"] = user_id
            request.scope["email"] = email
            
            logger.debug(f"Authenticated request to {path} for shop_id={shop_id}, user_id={user_id}")
            
            # Continue to route handler
            return await call_next(request)
            
        except jwt.ExpiredSignatureError:
            logger.warning(f"Expired token for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired"}
            )
        except jwt.InvalidSignatureError:
            logger.warning(f"Invalid token signature for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token signature"}
            )
        except jwt.DecodeError:
            logger.warning(f"Token decode error for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token format"}
            )
        except Exception as e:
            logger.error(f"Unexpected error validating token for {path}: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Token validation failed"}
            )
