# file: /opt/nornir-platform/app/security.py
import os
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext
from datetime import datetime, timedelta

from database import get_db_session, User

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "SuperSecretFallbackKey6789!!!")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a user password against its secure database hash string."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generates a secure hash string from plain text passwords."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Generates a secure, cryptographically signed JSON Web Token (JWT)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=60))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)) -> User:
    """Extracts and verifies users via standard HTTP Authorization Bearer headers."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate security credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    result = await db.execute(select(User).filter(User.username == username, User.is_active == True))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

async def get_ws_current_user(token: str = Query(..., alias="token"), db: AsyncSession = Depends(get_db_session)) -> User:
    """
    Alternative verification handler extracting tokens straight out of URL Query parameters.
    Bypasses standard HTTP header constraints specifically for secure WebSocket connections.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        result = await db.execute(select(User).filter(User.username == username, User.is_active == True))
        return result.scalars().first()
    except JWTError:
        return None

class RoleChecker:
    """Dependency guard verifying standard global-role clearance mappings."""
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)):
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account lacks the operational clearance required for this resource action."
            )
        return current_user

class ObjectPermissionGuard:
    """Granular security interceptor checking precise object and action criteria rules."""
    def __init__(self, object_type: str, action: str):
        self.object_type = object_type
        self.action = action

    async def __call__(self, target_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
        if current_user.role == "admin":
            return True

        from database import Permission, group_permission_association, Group
        query = select(Permission).join(group_permission_association).join(Group).\
            filter(Group.users.any(id=current_user.id)).\
            filter(Permission.object_type == self.object_type).\
            filter(Permission.action == self.action).\
            filter((Permission.object_id == target_id) | (Permission.object_id == "*"))

        result = await db.execute(query)
        if not result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied. Missing '{self.action}' clearance on {self.object_type} ID: {target_id}"
            )
        return True

