import pytest
from master import schemas
from master.db import models


@pytest.fixture
def setup_admin(db):
    from master.core.security import get_password_hash
    # Check if exists first (in case db session persists?)
    existing = db.query(models.User).filter_by(email="admin@example.com").first()
    if existing:
        return existing
        
    admin = models.User(
        email="admin@example.com",
        hashed_password=get_password_hash("StrongPass123!"),
        is_active=True,
        is_verified=True,
        role=models.UserRole.SUPER_ADMIN
    )
    db.add(admin)
    db.commit()
    return admin

def test_list_providers(client, db, setup_admin):
    # Login
    response = client.post("/api/v1/auth/login", json={
        "username": "admin@example.com",
        "password": "StrongPass123!"
    })
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test GET /providers
    response = client.get("/api/v1/communications/providers", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    
    # Check for SMTP
    smtp = next((p for p in data["providers"] if p["provider_name"] == "smtp"), None)
    assert smtp is not None
    assert "host" in smtp["config_schema"]
    assert "port" in smtp["config_schema"]
    
    # Check for SendPulse
    sendpulse = next((p for p in data["providers"] if p["provider_name"] == "sendpulse_api"), None)
    assert sendpulse is not None
    assert "api_id" in sendpulse["config_schema"]


def test_create_channel_validation(client, db, setup_admin):
    # Setup Auth
    response = client.post("/api/v1/auth/login", json={
        "username": "admin@example.com",
        "password": "StrongPass123!"
    })
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Invalid Provider
    response = client.post("/api/v1/communications/channels", headers=headers, json={
        "name": "Bad Provider",
        "channel_type": "email",
        "provider": "nonexistent",
        "config": {}
    })
    assert response.status_code == 400
    assert "Invalid provider" in response.json()["detail"]

    # 2. Invalid Config (Missing required fields for SMTP)
    response = client.post("/api/v1/communications/channels", headers=headers, json={
        "name": "Bad SMTP",
        "channel_type": "email",
        "provider": "smtp",
        "config": {
            "host": "smtp.gmail.com"
            # Missing port, username, password, etc.
        }
    })
    assert response.status_code == 400
    assert "Missing required config" in response.json()["detail"]

    assert "missing required config" in response.json()["detail"].lower()

    # 3. Invalid Email Format
    response = client.post("/api/v1/communications/channels", headers=headers, json={
        "name": "Bad Email SMTP",
        "channel_type": "email",
        "provider": "smtp",
        "config": {
            "host": "smtp.gmail.com",
            "port": 587,
            "username": "user",
            "password": "pass",
            "from_email": "not-an-email"
        }
    })
    assert response.status_code == 400
    assert "invalid 'from_email' format" in response.json()["detail"].lower()

    # 4. Invalid Config Type
    response = client.post("/api/v1/communications/channels", headers=headers, json={
        "name": "Bad Types SMTP",
        "channel_type": "email",
        "provider": "smtp",
        "config": {
            "host": 123, # Should be string
            "port": "not_an_int", # Should be int
            "username": "user",
            "password": "pass",
            "from_email": "test@example.com"
        }
    })
    assert response.status_code == 400
    assert "must be a string" in response.json()["detail"] or "must be an integer" in response.json()["detail"]

    # 4. Success
    response = client.post("/api/v1/communications/channels", headers=headers, json={
        "name": "Good SMTP",
        "channel_type": "email",
        "provider": "smtp",
        "config": {
            "host": "smtp.gmail.com",
            "port": 587,
            "username": "user",
            "password": "pass",
            "from_email": "test@example.com"
        }
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Good SMTP"


def test_update_channel_validation(client, db, setup_admin):
    # Setup Auth & Channel
    response = client.post("/api/v1/auth/login", json={
        "username": "admin@example.com",
        "password": "StrongPass123!"
    })
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create initial valid channel
    client.post("/api/v1/communications/channels", headers=headers, json={
        "name": "Update Test SMTP",
        "channel_type": "email",
        "provider": "smtp",
        "config": {
            "host": "smtp.gmail.com",
            "port": 587,
            "username": "user",
            "password": "pass",
            "from_email": "test@example.com"
        }
    })
    
    # Get ID
    channels = client.get("/api/v1/communications/channels", headers=headers).json()
    channel_id = channels["channels"][0]["id"]

    # Update with invalid config
    response = client.put(f"/api/v1/communications/channels/{channel_id}", headers=headers, json={
        "config": {
            "host": "smtp.gmail.com"
            # Missing others
        }
    })
    assert response.status_code == 400
    assert "Missing required config" in response.json()["detail"]

    # Update with valid config
    response = client.put(f"/api/v1/communications/channels/{channel_id}", headers=headers, json={
        "config": {
            "host": "smtp.office365.com",
            "port": 587,
            "username": "newuser",
            "password": "newpass",
            "from_email": "new@example.com"
        }
    })
    assert response.status_code == 200
    assert response.json()["provider"] == "smtp"
