import pytest
from master import schemas
from master.core.security import get_password_hash
from master.db import models

def test_login_rate_limit(client, db):
    # Create user
    user = models.User(
        email="ratelimit@example.com",
        hashed_password=get_password_hash("StrongPass123!"),
        is_active=True,
        is_verified=True,
        role=models.UserRole.SITE_ADMIN
    )
    db.add(user)
    db.commit()
    
    # Attempt 6 logins
    for i in range(6):
        response = client.post("/api/v1/auth/login", json={
            "username": "ratelimit@example.com",
            "password": "wrongpassword"
        })
        if i < 5:
            assert response.status_code == 400
        else:
            assert response.status_code == 429  # Too Many Requests

def test_idor_protection_in_verification(client, db):
    # Create unverified user
    user = models.User(
        email="unverified@example.com",
        hashed_password=get_password_hash("StrongPass123!"),
        is_active=True,
        is_verified=False,
        role=models.UserRole.SITE_ADMIN,
        email_verification_code="123456"
    )
    db.add(user)
    db.commit()

    # Login should fail but return verification token
    response = client.post("/api/v1/auth/login", json={
        "username": "unverified@example.com",
        "password": "StrongPass123!"
    })
    assert response.status_code == 403
    data = response.json()
    assert "verification_token" in data["detail"]
    token = data["detail"]["verification_token"]
    
    # Try to verify with wrong token (IDOR attempt)
    response = client.post("/api/v1/auth/verify-email", json={
        "code": "123456",
        "token": "invalid_token"
    })
    assert response.status_code == 401
    
    # Verify with correct token
    response = client.post("/api/v1/auth/verify-email", json={
        "code": "123456",
        "token": token
    })
    assert response.status_code == 200
    assert response.json()["success"] == True

def test_password_policy(client):
    # Test weak password
    try:
        schemas.UserCreate(
            email="weak@example.com",
            password="weak",
            role=models.UserRole.SITE_ADMIN
        )
        assert False, "Should have raised validation error"
    except ValueError:
        assert True

    # Test strong password
    schemas.UserCreate(
        email="strong@example.com",
        password="StrongPass123!",
        role=models.UserRole.SITE_ADMIN
    )
    assert True


def test_mfa_flow(client, db):
    # Setup: Create user and channel
    from master.core.encryption import encrypt_credential
    import json
    
    user = models.User(
        email="mfa_user@example.com",
        hashed_password=get_password_hash("StrongPass123!"),
        is_active=True,
        is_verified=True,
        role=models.UserRole.SITE_ADMIN
    )
    db.add(user)
    db.commit() # Initial commit to get ID
    
    # Create a valid encrypted config for the SMTP channel
    smtp_config = {
        "host": "smtp.test.com",
        "port": 587,
        "encryption": "tls",
        "username": "test@test.com",
        "password": "testpassword",
        "from_email": "noreply@test.com",
        "from_name": "Test"
    }
    
    channel = models.CommunicationChannel(
        name="Test Email",
        channel_type=models.ChannelType.EMAIL,
        provider="smtp",
        config_encrypted=encrypt_credential(json.dumps(smtp_config)),
        is_default=True
    )
    db.add(channel)
    db.commit()
    
    # 1. Login normally (MFA disabled)
    response = client.post("/api/v1/auth/login", json={
        "username": "mfa_user@example.com",
        "password": "StrongPass123!"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    # 2. Enable MFA (Initiate)
    # Note: enable_mfa expects json body with channel_id. 
    # schemas.MfaEnableRequest is the body.
    response = client.post(
        "/api/v1/auth/mfa/enable",
        json={"channel_id": channel.id},
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["mfa_required"] == True
    setup_token = data["mfa_token"]
    
    # Get OTP from DB
    db.refresh(user)
    setup_otp = user.login_otp
    assert setup_otp is not None
    
    # 3. Verify MFA Setup
    response = client.post("/api/v1/auth/mfa/verify", json={
        "code": setup_otp,
        "mfa_token": setup_token
    })
    assert response.status_code == 200
    
    # Verify enabled in DB
    db.refresh(user)
    assert user.mfa_enabled == True
    
    # 4. Login with MFA enabled -> Should return 200 (schema match) but with mfa_required=True
    response = client.post("/api/v1/auth/login", json={
        "username": "mfa_user@example.com",
        "password": "StrongPass123!"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["mfa_required"] == True
    assert data["mfa_token"] is not None
    login_token = data["mfa_token"]
    
    # 5. Verify Login MFA
    db.refresh(user)
    login_otp = user.login_otp
    
    # Verify with correct code
    response = client.post("/api/v1/auth/mfa/verify", json={
        "code": login_otp,
        "mfa_token": login_token
    })
    assert response.status_code == 200
    assert response.status_code == 200
    assert response.json()["access_token"]  # Real token

