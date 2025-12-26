from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
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
    turnstile_token: Optional[str] = None  # Cloudflare Turnstile token

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

# -- Extended Node Schemas --
class NodeDetailResponse(NodeBase):
    id: int
    status: str
    storage_quota_gb: int
    total_available_gb: int
    storage_used_gb: float = 0.0
    sites_count: int = 0
    backups_count: int = 0
    class Config:
        from_attributes = True

class NodeQuotaUpdate(BaseModel):
    storage_quota_gb: int

class NodeSimple(BaseModel):
    id: int
    hostname: str
    class Config:
        from_attributes = True

# -- Site Schemas --
class SiteResponse(SiteBase):
    id: int
    node_id: int
    status: str
    storage_used_gb: float = 0.0
    last_backup: Optional[datetime] = None
    class Config:
        from_attributes = True

class SiteListResponse(BaseModel):
    sites: List[SiteResponse]
    total: int

class SiteSimple(BaseModel):
    id: int
    name: str
    node_id: int
    class Config:
        from_attributes = True

# -- Backup Schemas --
class BackupResponse(BaseModel):
    id: int
    site_id: int
    site_name: str
    filename: str
    size_gb: float
    created_at: datetime
    backup_type: str
    status: str
    class Config:
        from_attributes = True

class BackupListResponse(BaseModel):
    backups: List[BackupResponse]
    total: int

# -- Activity Log Schemas --
class ActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class ActivityLogListResponse(BaseModel):
    logs: List[ActivityLogResponse]
    total: int

# -- Settings Schemas --
class SettingResponse(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class SettingUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None

class SettingsListResponse(BaseModel):
    settings: List[SettingResponse]
