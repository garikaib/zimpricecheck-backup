from pydantic import BaseModel, EmailStr
from typing import Optional, List
from master.db.models import UserRole

# -- User Schemas --
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: Optional[bool] = True
    role: UserRole = UserRole.SITE_ADMIN

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int

# -- Auth Schemas --
class LoginRequest(BaseModel):
    username: str
    password: str

# -- Token Schema --
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# -- Node Schemas --
class NodeBase(BaseModel):
    hostname: str
    ip_address: Optional[str] = None

class NodeCreate(NodeBase):
    pass

class NodeJoinRequest(NodeBase):
    system_info: Optional[str] = None # OS, versions etc

class NodeJoinResponse(BaseModel):
    request_id: str
    message: str

class NodeStatusResponse(BaseModel):
    status: str
    api_key: Optional[str] = None # Only present if approved

class NodeResponse(NodeBase):
    id: int
    status: str
    storage_quota_gb: int
    class Config:
        from_attributes = True

# -- Site Schemas --
class SiteBase(BaseModel):
    name: str
    wp_path: str
    db_name: Optional[str] = None

class SiteCreate(SiteBase):
    node_id: int
    admin_id: Optional[int] = None

# -- Stats Schemas --
class NodeStatsBase(BaseModel):
    cpu_usage: int
    disk_usage: int
    active_backups: int
    # logs: List[str] = [] # Potential future expansion

class NodeStatsCreate(NodeStatsBase):
    node_api_key: str # Simple auth for now
