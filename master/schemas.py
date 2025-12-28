from pydantic import BaseModel, EmailStr, field_validator
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
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Enforce strong password policy."""
        import re
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain a digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain special character')
        return v

class UserResponse(UserBase):
    id: int
    is_verified: bool = False
    pending_email: Optional[EmailStr] = None
    assigned_nodes: List[int] = []
    assigned_sites: List[int] = []
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
    mfa_required: bool = False
    mfa_token: Optional[str] = None

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
    uuid: Optional[str] = None
    status: str
    storage_quota_gb: int
    storage_used_bytes: int = 0
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

class SiteManualCreate(BaseModel):
    path: str
    wp_config_path: Optional[str] = None
    node_id: Optional[int] = None
    name: Optional[str] = None  # Optional override

class SiteVerifyRequest(BaseModel):
    path: str
    wp_config_path: Optional[str] = None

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
    uuid: Optional[str] = None
    status: str
    storage_quota_gb: int
    total_available_gb: int
    storage_used_bytes: int = 0
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
    uuid: Optional[str] = None
    node_id: int
    node_uuid: Optional[str] = None  # For structured storage paths
    status: str
    storage_used_bytes: int = 0
    storage_quota_gb: int = 10
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
class StorageProviderSimple(BaseModel):
    id: int
    name: str
    type: str
    class Config:
        from_attributes = True

class BackupResponse(BaseModel):
    id: int
    site_id: int
    site_name: str
    filename: str
    size_bytes: int
    size_gb: float
    s3_path: Optional[str] = None
    created_at: datetime
    backup_type: str
    status: str
    storage_provider: Optional[str] = None  # Provider name for list views
    class Config:
        from_attributes = True

class BackupDetailResponse(BackupResponse):
    """Extended backup response with full provider details."""
    storage_provider_detail: Optional[StorageProviderSimple] = None

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

# -- Storage Provider Schemas --
class StorageProviderCreate(BaseModel):
    name: str
    type: str = "s3"  # s3, b2, mega, local
    bucket: str
    region: Optional[str] = None
    endpoint: Optional[str] = None
    access_key: str
    secret_key: str
    is_default: bool = False
    storage_limit_gb: int = 100

class StorageProviderUpdate(BaseModel):
    name: Optional[str] = None
    bucket: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    is_default: Optional[bool] = None
    storage_limit_gb: Optional[int] = None
    is_active: Optional[bool] = None

class StorageProviderResponse(BaseModel):
    id: int
    name: str
    type: str
    bucket: str
    region: Optional[str] = None
    endpoint: Optional[str] = None
    is_default: bool
    storage_limit_gb: int
    used_gb: float = 0.0
    is_active: bool
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class StorageProviderListResponse(BaseModel):
    providers: List[StorageProviderResponse]

class NodeStorageSummary(BaseModel):
    node_id: int
    hostname: str
    quota_gb: int
    used_gb: float
    available_gb: float
    usage_percentage: float
    status: str

class StorageSummaryResponse(BaseModel):
    total_quota_gb: float
    total_used_gb: float
    total_available_gb: float
    usage_percentage: float
    nodes_count: int
    nodes_summary: List[NodeStorageSummary]
    storage_providers: List[StorageProviderResponse]

class StorageTestResponse(BaseModel):
    success: bool
    message: str
    available_space_gb: Optional[float] = None


# -- Communication Channel Schemas --
class CommunicationChannelCreate(BaseModel):
    name: str
    channel_type: str  # email, sms, whatsapp, push
    provider: str  # sendpulse_api, smtp, twilio, etc.
    config: dict  # Provider-specific configuration (will be encrypted)
    allowed_roles: Optional[List[str]] = None  # verification, notification, etc.
    is_default: bool = False
    priority: int = 10


class CommunicationChannelUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    allowed_roles: Optional[List[str]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class CommunicationChannelResponse(BaseModel):
    id: int
    name: str
    channel_type: str
    provider: str
    allowed_roles: Optional[List[str]] = None
    is_default: bool
    is_active: bool
    priority: int
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


class CommunicationChannelListResponse(BaseModel):
    channels: List[CommunicationChannelResponse]
    total: int


class CommunicationTestRequest(BaseModel):
    to: str  # Recipient for test message


class CommunicationTestResponse(BaseModel):
    success: bool
    message: str
    provider: Optional[str] = None


# -- Verification Schemas --
class VerifyEmailRequest(BaseModel):
    code: str
    token: Optional[str] = None  # Verification token for IDOR protection


class VerifyEmailResponse(BaseModel):
    success: bool
    message: str


# -- MFA Schemas --
class MfaEnableRequest(BaseModel):
    channel_id: int

class MfaVerifyRequest(BaseModel):
    code: str
    mfa_token: Optional[str] = None


class ResendVerificationRequest(BaseModel):
    email: Optional[EmailStr] = None  # Optional, uses current user if not provided


class ConfirmEmailChangeRequest(BaseModel):
    code: str
    force_verify: bool = False  # Super Admin only: skip code verification


# -- Magic Link Schemas --
class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    success: bool
    message: str


# -- Node/Site Assignment Schemas --
class NodeAssignment(BaseModel):
    node_ids: List[int]


class SiteAssignment(BaseModel):
    site_ids: List[int]


class AssignmentResponse(BaseModel):
    message: str
    assigned: List[int]


# -- Provider Schemas --
class ProviderSchemaResponse(BaseModel):
    channel_type: str
    provider_name: str
    config_schema: dict

class ProviderListResponse(BaseModel):
    providers: List[ProviderSchemaResponse]

