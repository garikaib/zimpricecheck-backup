from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum
import datetime

Base = declarative_base()

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    NODE_ADMIN = "node_admin"
    SITE_ADMIN = "site_admin"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(UserRole), default=UserRole.SITE_ADMIN)
    
    # Relationships
    nodes = relationship("Node", back_populates="admin")
    sites = relationship("Site", back_populates="admin")

class NodeStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"

class Node(Base):
    __tablename__ = "nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, index=True)
    ip_address = Column(String)
    api_key = Column(String, unique=True, index=True)  # For agent authentication
    is_active = Column(Boolean, default=True)
    status = Column(Enum(NodeStatus), default=NodeStatus.PENDING)
    storage_quota_gb = Column(Integer, default=100)
    total_available_gb = Column(Integer, default=1000)
    
    # Ownership (Node Admin)
    admin_id = Column(Integer, ForeignKey("users.id"))
    admin = relationship("User", back_populates="nodes")
    
    sites = relationship("Site", back_populates="node")
    stats = relationship("NodeStats", back_populates="node")

class Site(Base):
    __tablename__ = "sites"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    wp_path = Column(String)
    db_name = Column(String)
    status = Column(String, default="active")  # active, paused, error
    storage_used_bytes = Column(Integer, default=0)
    
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

class NodeStats(Base):
    __tablename__ = "node_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("nodes.id"))
    node = relationship("Node", back_populates="stats")
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    cpu_usage = Column(Integer) # Percentage
    disk_usage = Column(Integer) # Percentage
    active_backups = Column(Integer)
