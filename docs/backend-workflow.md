---
description: Backend development workflow for WordPress Backup SaaS Master Server
---

# Backend Development Workflow

## Project Overview

- **Local Repo**: `/home/garikaib/Documents/source/wordpress-backup`
- **Tech Stack**: FastAPI, SQLAlchemy, SQLite, Pydantic
- **Production URL**: `https://wp.zimpricecheck.com:8081/api/v1`
- **SSH Access**: `ssh -p 2200 ubuntu@wp.zimpricecheck.com`
- **Remote Install Dir**: `/opt/wordpress-backup`

---

## Key Files

| Purpose | Path |
|---------|------|
| **Models** | `master/db/models.py` |
| **Schemas** | `master/schemas.py` |
| **Dependencies** | `master/api/deps.py` |
| **Endpoints** | `master/api/v1/endpoints/*.py` |
| **Router Registration** | `master/main.py` |
| **Config** | `master/core/config.py` |
| **Security** | `master/core/security.py` |
| **Activity Logger** | `master/core/activity_logger.py` |
| **Deploy Script** | `deploy.sh` |
| **API Docs** | `docs/api_reference.md` |

---

## Development Flow

### 1. Make Code Changes

```bash
# Edit files locally
# Key locations:
# - New endpoint: master/api/v1/endpoints/<name>.py
# - Register in: master/main.py
# - Add schemas: master/schemas.py
# - Add models: master/db/models.py
```

### 2. Syntax Check

```bash
cd /home/garikaib/Documents/source/wordpress-backup/master
python3 -m py_compile main.py schemas.py db/models.py api/v1/endpoints/<file>.py
```

### 3. Deploy to Production

```bash
cd /home/garikaib/Documents/source/wordpress-backup
./deploy.sh master
```

The deploy script:
- Creates bundle of master server files
- Uploads to `/opt/wordpress-backup` via SSH (port 2200)
- Clears Python cache
- Runs database initialization
- Restarts `wordpress-master` systemd service
- Verifies service is running

### 4. Database Migrations

If you added new columns/tables, run manually:

```bash
ssh -p 2200 ubuntu@wp.zimpricecheck.com "cd /opt/wordpress-backup && sqlite3 master.db 'ALTER TABLE <table> ADD COLUMN <column> <type> DEFAULT <value>;'"
```

Or for new tables:
```bash
ssh -p 2200 ubuntu@wp.zimpricecheck.com "cd /opt/wordpress-backup && sqlite3 master.db 'CREATE TABLE IF NOT EXISTS <table> (...);'"
```

### 5. Test Endpoints

```bash
# Login
TOKEN=$(curl -s -X POST https://wp.zimpricecheck.com:8081/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@example.com","password":"admin123"}' | jq -r '.access_token')

# Test authenticated endpoint
curl -s https://wp.zimpricecheck.com:8081/api/v1/<endpoint> \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### 6. Commit & Push

```bash
git add .
git commit -m "feat/fix: <description>"
git push origin main
```

---

## Common Patterns

### Adding a New Endpoint File

1. Create `master/api/v1/endpoints/<name>.py`
2. Import and register in `master/main.py`:
   ```python
   from master.api.v1.endpoints import ..., <name>
   api_router.include_router(<name>.router, prefix="/<name>", tags=["<name>"])
   ```

### Adding Activity Logging

```python
from master.core.activity_logger import log_action

# In endpoint:
log_action(
    action=models.ActionType.<ACTION>,
    user=current_user,
    request=request,  # For IP/user-agent
    target_type="<type>",
    target_id=<id>,
    target_name="<name>",
    details={"key": "value"},
)
```

### Role-Based Access

```python
# Super Admin only
current_superuser: models.User = Depends(deps.get_current_superuser)

# Node Admin or higher
current_user: models.User = Depends(deps.get_current_node_admin_or_higher)

# Any authenticated user
current_user: models.User = Depends(deps.get_current_active_user)
```

---

## Debugging

### Check Server Logs
```bash
ssh -p 2200 ubuntu@wp.zimpricecheck.com "sudo journalctl -u wordpress-master -n 50 --no-pager"
```

### Restart Service
```bash
ssh -p 2200 ubuntu@wp.zimpricecheck.com "sudo systemctl restart wordpress-master"
```

### Check Database
```bash
ssh -p 2200 ubuntu@wp.zimpricecheck.com "cd /opt/wordpress-backup && sqlite3 master.db '.tables'"
ssh -p 2200 ubuntu@wp.zimpricecheck.com "cd /opt/wordpress-backup && sqlite3 master.db 'SELECT * FROM users;'"
```

---

## User Roles

| Role | Value | Access |
|------|-------|--------|
| Super Admin | `super_admin` | Full access |
| Node Admin | `node_admin` | Manage assigned nodes |
| Site Admin | `site_admin` | View own profile only |

---

## Test Credentials

- **Email**: `admin@example.com`
- **Password**: `admin123`
- **Role**: `super_admin`
