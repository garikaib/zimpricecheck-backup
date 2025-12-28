from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum, Table
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum
import datetime
import uuid

Base = declarative_base()


# Association tables for user role-based assignments
user_nodes = Table(
    "user_nodes",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("node_id", Integer, ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime, default=datetime.datetime.utcnow),
)

user_sites = Table(
    "user_sites",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("site_id", Integer, ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime, default=datetime.datetime.utcnow),
)

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    NODE_ADMIN = "node_admin"
    SITE_ADMIN = "site_admin"


class ChannelType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"


class MessageRole(str, enum.Enum):
    VERIFICATION = "verification"
    NOTIFICATION = "notification"
    ALERT = "alert"
    MARKETING = "marketing"
    TRANSACTIONAL = "transactional"
    LOGIN_LINK = "login_link"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(UserRole), default=UserRole.SITE_ADMIN)
    
    # Email verification
    is_verified = Column(Boolean, default=False)
    email_verification_code = Column(String, nullable=True)
    email_verification_expires = Column(DateTime, nullable=True)
    pending_email = Column(String, nullable=True)

    # Magic link login
    magic_link_token = Column(String, nullable=True, index=True)
    magic_link_expires = Column(DateTime, nullable=True)

    # MFA
    mfa_enabled = Column(Boolean, default=False)
    mfa_channel_id = Column(Integer, ForeignKey("communication_channels.id"), nullable=True)
    login_otp = Column(String, nullable=True)
    login_otp_expires = Column(DateTime, nullable=True)
    
    # Relationships (admin ownership)
    nodes = relationship("Node", back_populates="admin")
    sites = relationship("Site", back_populates="admin")
    
    # Role-based assignments (many-to-many)
    assigned_nodes = relationship("Node", secondary=user_nodes, backref="assigned_users")
    assigned_sites = relationship("Site", secondary=user_sites, backref="assigned_users")

class NodeStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"

class Node(Base):
    __tablename__ = "nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    hostname = Column(String, index=True)
    ip_address = Column(String)
    api_key = Column(String, unique=True, index=True)  # For agent authentication
    is_active = Column(Boolean, default=True)
    status = Column(Enum(NodeStatus), default=NodeStatus.PENDING)
    storage_quota_gb = Column(Integer, default=100)
    storage_used_bytes = Column(Integer, default=0)  # Track actual usage
    total_available_gb = Column(Integer, default=1000)
    
    # Scheduling Limits
    max_retention_copies = Column(Integer, default=10) # Max copies per site
    max_concurrent_backups = Column(Integer, default=2) # Max simultaneous backups per node
    
    registration_code = Column(String(5), nullable=True, index=True)  # 5-char code for registration
    
    # Ownership (Node Admin)
    admin_id = Column(Integer, ForeignKey("users.id"))
    admin = relationship("User", back_populates="nodes")
    
    sites = relationship("Site", back_populates="node")
    stats = relationship("NodeStats", back_populates="node")

class Site(Base):
    __tablename__ = "sites"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    wp_path = Column(String)
    db_name = Column(String)
    status = Column(String, default="active")  # active, paused, error
    site_url = Column(String, nullable=True) # Public URL of the site
    storage_used_bytes = Column(Integer, default=0)
    storage_quota_gb = Column(Integer, default=10)  # Per-site quota
    
    # Backup status tracking
    backup_status = Column(String, default="idle")  # idle, running, completed, failed
    backup_progress = Column(Integer, default=0)
    backup_started_at = Column(DateTime, nullable=True)
    backup_message = Column(String, nullable=True)
    backup_error = Column(String, nullable=True)
    
    # Granular stage tracking
    backup_stage = Column(String, nullable=True)  # Current stage name: backup_db, backup_files, etc.
    backup_stage_detail = Column(String, nullable=True)  # Sub-step: "Exporting table wp_posts..."
    backup_bytes_processed = Column(Integer, default=0)  # Bytes processed in current stage
    backup_bytes_total = Column(Integer, default=0)  # Total bytes expected
    
    # Quota tracking
    quota_exceeded_at = Column(DateTime, nullable=True)  # When quota first exceeded
    
    # Schedule Configuration
    schedule_frequency = Column(String, default="manual")  # manual, daily, weekly, monthly
    schedule_time = Column(String, nullable=True)  # HH:MM (Africa/Harare)
    schedule_days = Column(String, nullable=True)  # CSV: 0,1,2 (Mon,Tue,Wed) or 1 (Day of month)
    retention_copies = Column(Integer, default=5)  # Number of backups to retain
    next_run_at = Column(DateTime, nullable=True)  # Calculated next run (UTC or Aware)
    
    # Belongs to a Node
    node_id = Column(Integer, ForeignKey("nodes.id"))
    node = relationship("Node", back_populates="sites")
    
    # Managed by Site Admin
    admin_id = Column(Integer, ForeignKey("users.id"))
    admin = relationship("User", back_populates="sites")
    
    backups = relationship("Backup", back_populates="site")

class Backup(Base):
    __tablename__ = "backups"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    s3_path = Column(String)
    size_bytes = Column(Integer)
    status = Column(String)  # SUCCESS, ERROR
    backup_type = Column(String, default="full")  # full, incremental
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    site_id = Column(Integer, ForeignKey("sites.id"))
    site = relationship("Site", back_populates="backups")
    
    provider_id = Column(Integer, ForeignKey("storage_providers.id"), nullable=True)
    provider = relationship("StorageProvider", back_populates="backups")
    
    # Auto-cleanup scheduling
    scheduled_deletion = Column(DateTime, nullable=True)  # Auto-delete after this date

class NodeStats(Base):
    __tablename__ = "node_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("nodes.id"))
    node = relationship("Node", back_populates="stats")
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    cpu_usage = Column(Integer) # Percentage
    disk_usage = Column(Integer) # Percentage
    active_backups = Column(Integer)


class ActionType(str, enum.Enum):
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    PROFILE_UPDATE = "profile_update"
    NODE_APPROVE = "node_approve"
    NODE_QUOTA_UPDATE = "node_quota_update"
    NODE_BLOCK = "node_block"
    BACKUP_DELETE = "backup_delete"


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_email = Column(String, nullable=True)  # Store email for lookup even if user deleted
    action = Column(Enum(ActionType), index=True)
    target_type = Column(String, nullable=True)  # "user", "node", "backup", etc.
    target_id = Column(Integer, nullable=True)
    target_name = Column(String, nullable=True)  # Readable identifier
    details = Column(String, nullable=True)  # JSON string for extra info
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class Settings(Base):
    """Key-value store for application settings."""
    __tablename__ = "settings"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=True)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class ProviderType(str, enum.Enum):
    S3 = "s3"
    B2 = "b2"
    MEGA = "mega"
    LOCAL = "local"


class StorageProvider(Base):
    """Storage provider configuration with encrypted credentials."""
    __tablename__ = "storage_providers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    type = Column(Enum(ProviderType), default=ProviderType.S3)
    bucket = Column(String, nullable=False)
    region = Column(String, nullable=True)
    endpoint = Column(String, nullable=True)  # For S3-compatible (Wasabi, Backblaze, etc.)
    access_key_encrypted = Column(String, nullable=True)  # Encrypted at rest
    secret_key_encrypted = Column(String, nullable=True)  # Encrypted at rest
    is_default = Column(Boolean, default=False, index=True)
    storage_limit_gb = Column(Integer, default=100)
    used_bytes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    backups = relationship("Backup", back_populates="provider")


class CommunicationChannel(Base):
    """Communication channel configuration (email, SMS, WhatsApp, push)."""
    __tablename__ = "communication_channels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    channel_type = Column(Enum(ChannelType), nullable=False, index=True)
    provider = Column(String, nullable=False)  # "sendpulse_api", "smtp", "twilio", etc.
    config_encrypted = Column(String, nullable=True)  # JSON config (encrypted)
    allowed_roles = Column(String, nullable=True)  # JSON list: ["verification", "notification"]
    is_default = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=10)  # Lower = higher priority (for failover)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
