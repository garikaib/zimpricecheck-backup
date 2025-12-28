import pytest
from master.db import models
from master.core.security import get_password_hash
from master.api import deps

def create_user(db, email, role, password="Test@Pass12!"):
    user = models.User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=f"Test {role}",
        role=role,
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_node(db, hostname="node1", admin=None):
    node = models.Node(
        hostname=hostname,
        ip_address="1.2.3.4",
        status=models.NodeStatus.ACTIVE,
        storage_quota_gb=100
    )
    if admin:
        # Legacy field, but also need to assign via M:N
        node.admin_id = admin.id 
    db.add(node)
    db.commit()
    db.refresh(node)
    return node

def create_site(db, node, name="site1", admin=None):
    site = models.Site(
        name=name,
        wp_path=f"/var/www/{name}",
        node_id=node.id,
        status="active"
    )
    if admin:
        site.admin_id = admin.id
    db.add(site)
    db.commit()
    db.refresh(site)
    return site

def test_validate_node_access(db):
    # Setup users
    super_admin = create_user(db, "super@test.com", models.UserRole.SUPER_ADMIN)
    node_admin = create_user(db, "node@test.com", models.UserRole.NODE_ADMIN)
    other_node_admin = create_user(db, "other_node@test.com", models.UserRole.NODE_ADMIN)
    site_admin = create_user(db, "site@test.com", models.UserRole.SITE_ADMIN)
    
    # Setup resources
    node = create_node(db, "test-node")
    
    # Assign node to node_admin
    node_admin.assigned_nodes.append(node)
    db.commit()
    
    # Check Super Admin (Always True)
    assert deps.validate_node_access(super_admin, node.id) is True
    
    # Check Assigned Node Admin (True)
    assert deps.validate_node_access(node_admin, node.id) is True
    
    # Check Unassigned Node Admin (False)
    assert deps.validate_node_access(other_node_admin, node.id) is False
    
    # Check Site Admin (False - Site Admins don't manage nodes)
    assert deps.validate_node_access(site_admin, node.id) is False

def test_validate_site_access(db):
    # Setup users
    super_admin = create_user(db, "super2@test.com", models.UserRole.SUPER_ADMIN)
    node_admin = create_user(db, "node2@test.com", models.UserRole.NODE_ADMIN)
    other_node_admin = create_user(db, "other_node2@test.com", models.UserRole.NODE_ADMIN)
    site_admin = create_user(db, "site2@test.com", models.UserRole.SITE_ADMIN)
    other_site_admin = create_user(db, "other_site2@test.com", models.UserRole.SITE_ADMIN)
    
    # Setup resources
    node = create_node(db, "test-node-2")
    site = create_site(db, node, "test-site")
    
    # Assignments
    node_admin.assigned_nodes.append(node)
    site_admin.assigned_sites.append(site)
    db.commit()
    db.refresh(node_admin)
    db.refresh(site_admin)
    
    # Super Admin Access
    assert deps.validate_site_access(super_admin, site) is True
    
    # Node Admin Access (via Node Assignment)
    # Allows access because site.node_id is in assigned_nodes
    assert deps.validate_site_access(node_admin, site) is True
    
    # Other Node Admin Access (False)
    assert deps.validate_site_access(other_node_admin, site) is False
    
    # Site Admin Access (via Site Assignment)
    assert deps.validate_site_access(site_admin, site) is True
    
    # Other Site Admin Access (False)
    assert deps.validate_site_access(other_site_admin, site) is False
@pytest.mark.skip(reason="Requires daemon API mocking - RBAC logic tested via unit tests")

def test_unauthorized_site_access(client, db):
    # Create Site Admin with NO assignments
    site_admin_user = create_user(db, "bad_admin@test.com", models.UserRole.SITE_ADMIN)
    node = create_node(db, "secure-node")
    site = create_site(db, node, "secure-site")
    
    def override_current_user():
        return site_admin_user
        
    client.app.dependency_overrides[deps.get_current_active_user] = override_current_user
    
    # Try to access site details
    response = client.get(f"/api/v1/sites/{site.id}")
    assert response.status_code == 403
    
    # Try to backup
    response = client.post(f"/api/v1/sites/{site.id}/backup/stop")
    assert response.status_code == 403
