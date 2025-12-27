from typing import Generator
import logging
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from master.core.config import get_settings
from master.core import security
from master.db.session import SessionLocal
from master.db import models
from master import schemas

# Setup logging for debugging auth issues
logger = logging.getLogger(__name__)

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def verify_token_string(token: str, db: Session) -> models.User:
    """
    Verify a JWT token string and return the user.
    Used for query parameter authentication (e.g., SSE streaming).
    
    Raises HTTPException if token is invalid.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing 'sub' claim",
            )
        
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            )
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
        )

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> models.User:
    print(f"[AUTH] Token validation starting...")
    print(f"[AUTH] Token (first 50 chars): {token[:50] if len(token) > 50 else token}...")
    print(f"[AUTH] Using SECRET_KEY (first 10 chars): {settings.SECRET_KEY[:10]}...")
    print(f"[AUTH] Using ALGORITHM: {settings.ALGORITHM}")
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        print(f"[AUTH] Token decoded successfully!")
        print(f"[AUTH] Payload: {payload}")
        
        email: str = payload.get("sub")
        if email is None:
            print("[AUTH] Token missing 'sub' claim!")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing 'sub' claim",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token_data = schemas.TokenData(email=email)
        print(f"[AUTH] Looking up user with email: {email}")
        
    except jwt.ExpiredSignatureError:
        print("[AUTH] Token has expired!")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTClaimsError as e:
        print(f"[AUTH] JWT claims error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        print(f"[AUTH] JWT decode error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(models.User).filter(models.User.email == token_data.email).first()
    if user is None:
        print(f"[AUTH] User not found in database: {token_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"[AUTH] User authenticated successfully: {user.email} (role: {user.role})")
    return user

def get_current_active_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_superuser(
    current_user: models.User = Depends(get_current_active_user),
) -> models.User:
    if current_user.role != models.UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user

def get_current_node_admin_or_higher(
    current_user: models.User = Depends(get_current_active_user),
) -> models.User:
    """Allow Node Admins and Super Admins."""
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.NODE_ADMIN]:
        raise HTTPException(
            status_code=403, detail="Insufficient privileges"
        )
    return current_user


def get_current_node(
    request: Request,
    db: Session = Depends(get_db),
) -> models.Node:
    """
    Authenticate node via X-API-KEY header.
    Used for node-to-master API calls (e.g., fetching storage config).
    """
    print(f"[NODE AUTH] get_current_node called")
    api_key = request.headers.get("X-API-KEY")
    print(f"[NODE AUTH] X-API-KEY: {api_key[:20]}..." if api_key else "[NODE AUTH] X-API-KEY: None")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    
    node = db.query(models.Node).filter(models.Node.api_key == api_key).first()
    if not node:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    
    if node.status != models.NodeStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Node is not active",
        )
    
    return node
