# SaaS Master Server Reference

The Master Server provides the REST API for the Backup Platform.

## Authentication
*   **JWT**: All protected endpoints require `Authorization: Bearer <token>`.
*   **API Key**: Nodes authenticate via header `X-API-KEY: <key>`.

## API Endpoints

### Authentication
*   `POST /api/v1/auth/login`
    *   **Content-Type**: `application/json`
    *   **Body**: 
        ```json
        {
          "username": "admin@example.com",
          "password": "yourpassword"
        }
        ```
    *   **Return**: Access Token (JWT)

### Node Management (Public/Agent)
*   `POST /api/v1/nodes/join-request`
    *   **Body**: `hostname`, `ip_address`, `system_info`
    *   **Return**: `request_id`
    *   **Desc**: Submit a new node for approval.
*   `GET /api/v1/nodes/status/{request_id}`
    *   **Return**: `status` ("pending"|"active"|"blocked"). If active, includes `api_key`.
    *   **Desc**: Polled by agents during setup.

### Node Management (Admin)
*   `POST /api/v1/nodes/approve/{node_id}`
    *   **Auth**: Super Admin
    *   **Desc**: Approves a pending node, generating its API key.
*   `GET /api/v1/nodes/`
    *   **Auth**: Super Admin
    *   **Desc**: List all nodes.

### Statistics
*   `POST /api/v1/stats/`
    *   **Auth**: Node API Key
    *   **Body**: `cpu_usage`, `disk_usage`, `active_backups`
    *   **Desc**: Heartbeat endpoint for nodes.

## Admin Config

Configuration is handled via `.env` in the `master/` directory (created during deployment).

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy Connection String | `sqlite:///./master.db` |
| `SECRET_KEY` | JWT Signing Key | (Change in Prod) |
| `FIRST_SUPERUSER` | Initial Admin Email | `admin@example.com` |
| `FIRST_SUPERUSER_PASSWORD` | Initial Admin Pass | `admin123` |

## User Management

> **See also**: [Users API Reference](users.md) for full endpoint documentation.

### Roles

| Role | Access Level |
|------|--------------|
| `super_admin` | Full system access |
| `node_admin` | Manage nodes + Site Admins on their nodes |
| `site_admin` | Manage own sites only |

### API Endpoints (Summary)

| Endpoint | Method | Access |
|----------|--------|--------|
| `/api/v1/users/me` | GET | Any authenticated |
| `/api/v1/users/` | GET | Node Admin+ |
| `/api/v1/users/` | POST | Super Admin |
| `/api/v1/users/{id}` | GET/PUT | Node Admin+ |
| `/api/v1/users/{id}` | DELETE | Super Admin |

### 1. Initial Super Admin
When you first deploy the Master Server, an initial Super Admin is created based on the `.env` variables above. 
Logs: `[*] Creating first superuser: admin@example.com`

### 2. Adding More Admins
You can manage Super Admins interactively via the configuration script on the Master Server:

```bash
# SSH into Master
ssh ubuntu@<master-ip>
cd /opt/wordpress-backup-master

# Launch Admin Manager
./configure.sh --add-admin
```
This utility allows you to:
-   **List** current admins.
-   **Add** new admins.
-   **Modify** existing admins (reset passwords).
