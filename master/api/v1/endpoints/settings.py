from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models
from master.core.activity_logger import log_action

router = APIRouter()


# Known settings keys
SETTING_KEYS = {
    "turnstile_secret": "Cloudflare Turnstile Secret Key",
    "turnstile_site_key": "Cloudflare Turnstile Site Key",
    "turnstile_enabled": "Enable Turnstile verification (true/false)",
}


@router.get("/", response_model=schemas.SettingsListResponse)
def read_settings(
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: List all settings.
    """
    settings = db.query(models.Settings).all()
    return {"settings": settings}


@router.get("/{key}", response_model=schemas.SettingResponse)
def read_setting(
    key: str,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Get a specific setting.
    """
    setting = db.query(models.Settings).filter(models.Settings.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.put("/{key}", response_model=schemas.SettingResponse)
def update_setting(
    key: str,
    setting_in: schemas.SettingUpdate,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Update or create a setting.
    """
    setting = db.query(models.Settings).filter(models.Settings.key == key).first()
    
    if setting:
        old_value = setting.value
        if setting_in.value is not None:
            setting.value = setting_in.value
        if setting_in.description is not None:
            setting.description = setting_in.description
    else:
        # Create new setting
        old_value = None
        setting = models.Settings(
            key=key,
            value=setting_in.value,
            description=setting_in.description or SETTING_KEYS.get(key, ""),
        )
        db.add(setting)
    
    db.commit()
    db.refresh(setting)
    
    # Log the change
    log_action(
        action=models.ActionType.PROFILE_UPDATE,  # Reusing for settings
        user=current_superuser,
        target_type="setting",
        target_name=key,
        details={"old_value": old_value, "new_value": setting.value},
    )
    
    return setting


@router.get("/public/turnstile-site-key")
def get_turnstile_site_key(
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Public: Get Turnstile site key for frontend.
    """
    setting = db.query(models.Settings).filter(models.Settings.key == "turnstile_site_key").first()
    if not setting or not setting.value:
        return {"site_key": None, "enabled": False}
    
    enabled_setting = db.query(models.Settings).filter(models.Settings.key == "turnstile_enabled").first()
    enabled = enabled_setting.value == "true" if enabled_setting else False
    
    return {"site_key": setting.value, "enabled": enabled}
