"""Tests for site endpoints, particularly schedule fields persistence."""
import pytest
from master.db.models import User, Node, Site, UserRole
from master.core.security import get_password_hash


def create_test_user(db, email="admin@test.com", role=UserRole.SUPER_ADMIN):
    """Create a test user."""
    user = User(
        email=email,
        hashed_password=get_password_hash("TestPass123!@#"),
        full_name="Test Admin",
        is_active=True,
        is_verified=True,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_node(db):
    """Create a test node."""
    node = Node(
        hostname="test-node",
        ip_address="192.168.1.1",
        api_key="test-api-key-12345",
        status="active",
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def create_test_site(db, node, schedule_frequency="daily", schedule_time="02:00"):
    """Create a test site with schedule."""
    site = Site(
        name="example.com",
        wp_path="/var/www/example/htdocs",
        db_name="example_db",
        node_id=node.id,
        status="active",
        schedule_frequency=schedule_frequency,
        schedule_time=schedule_time,
        schedule_days="0,2,4",
        retention_copies=7,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def get_auth_token(client, email="admin@test.com", password="TestPass123!@#"):
    """Get auth token for testing."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    return response.json()["access_token"]


class TestSiteScheduleFields:
    """Test that schedule fields are returned in site endpoints."""

    def test_get_sites_includes_schedule_fields(self, client, db):
        """GET /sites/ should include schedule fields."""
        # Setup
        user = create_test_user(db)
        node = create_test_node(db)
        site = create_test_site(db, node, schedule_frequency="weekly", schedule_time="03:30")
        
        # Get auth token
        token = get_auth_token(client)
        
        # Make request
        response = client.get(
            "/api/v1/sites/",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "sites" in data
        assert len(data["sites"]) >= 1
        
        # Find our test site
        test_site = next((s for s in data["sites"] if s["name"] == "example.com"), None)
        assert test_site is not None, "Test site not found in response"
        
        # Verify schedule fields are present
        assert "schedule_frequency" in test_site
        assert "schedule_time" in test_site
        assert "schedule_days" in test_site
        assert "retention_copies" in test_site
        assert "next_run_at" in test_site
        
        # Verify values
        assert test_site["schedule_frequency"] == "weekly"
        assert test_site["schedule_time"] == "03:30"
        assert test_site["schedule_days"] == "0,2,4"
        assert test_site["retention_copies"] == 7

    def test_get_single_site_includes_schedule_fields(self, client, db):
        """GET /sites/{id} should include schedule fields."""
        # Setup
        user = create_test_user(db)
        node = create_test_node(db)
        site = create_test_site(db, node, schedule_frequency="monthly", schedule_time="04:00")
        
        # Get auth token
        token = get_auth_token(client)
        
        # Make request
        response = client.get(
            f"/api/v1/sites/{site.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify schedule fields are present
        assert "schedule_frequency" in data
        assert "schedule_time" in data
        assert "schedule_days" in data
        assert "retention_copies" in data
        assert "next_run_at" in data
        
        # Verify values
        assert data["schedule_frequency"] == "monthly"
        assert data["schedule_time"] == "04:00"
        assert data["schedule_days"] == "0,2,4"
        assert data["retention_copies"] == 7

    def test_update_schedule_persists_to_get(self, client, db):
        """PUT /sites/{id}/schedule should persist and be reflected in GET."""
        # Setup
        user = create_test_user(db)
        node = create_test_node(db)
        site = create_test_site(db, node, schedule_frequency="manual", schedule_time=None)
        
        # Get auth token
        token = get_auth_token(client)
        
        # Update schedule
        update_response = client.put(
            f"/api/v1/sites/{site.id}/schedule",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "schedule_frequency": "daily",
                "schedule_time": "02:00",
                "schedule_days": "1,3,5",
                "retention_copies": 5,
            },
        )
        
        assert update_response.status_code == 200
        
        # Fetch site and verify schedule persisted
        get_response = client.get(
            f"/api/v1/sites/{site.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert get_response.status_code == 200
        data = get_response.json()
        
        assert data["schedule_frequency"] == "daily"
        assert data["schedule_time"] == "02:00"
        assert data["schedule_days"] == "1,3,5"
        assert data["retention_copies"] == 5

    def test_schedule_defaults_to_manual(self, client, db):
        """Sites without schedule should default to 'manual'."""
        # Setup
        user = create_test_user(db)
        node = create_test_node(db)
        
        # Create site without explicit schedule
        site = Site(
            name="noSchedule.com",
            wp_path="/var/www/noSchedule/htdocs",
            node_id=node.id,
            status="active",
        )
        db.add(site)
        db.commit()
        db.refresh(site)
        
        # Get auth token
        token = get_auth_token(client)
        
        # Fetch site
        response = client.get(
            f"/api/v1/sites/{site.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should default to "manual"
        assert data["schedule_frequency"] == "manual"
        assert data["retention_copies"] == 5  # Default
