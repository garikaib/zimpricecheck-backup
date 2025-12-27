# SaaS Master Server Reference

The Master Server provides the REST API for the Backup Platform.

## Authentication
*   **JWT**: All protected user endpoints require `Authorization: Bearer <token>`.
*   **API Key**: Nodes authenticate via header `X-API-KEY: <key>`.

See [Authentication API](api/authentication.md) for details.

## API Documentation

For full endpoint details, please refer to the **[API Reference Directory](api/README.md)**.

*   **[Nodes API](api/nodes.md)**: Manage nodes, approvals, and join requests.
*   **[Users API](api/users.md)**: Manage users and roles.
*   **[Sites API](api/sites.md)**: Manage sites and quota checks.
*   **[Storage API](api/storage.md)**: Manage storage providers and reconciliation.
*   **[Backups API](api/backups.md)**: Manage backup archives.

## Admin Config

Configuration is handled via `.env` in the `master/` directory (created during deployment).

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy Connection String | `postgresql+psycopg2://...` |
| `SECRET_KEY` | JWT Signing Key | (Change in Prod) |
| `FIRST_SUPERUSER` | Initial Admin Email | `admin@example.com` |
| `FIRST_SUPERUSER_PASSWORD` | Initial Admin Pass | `admin123` |

## CLI Management

### Adding Admins
You can manage Super Admins interactively via the configuration script on the Master Server:

```bash
# SSH into Master
ssh ubuntu@<master-ip>
cd /opt/wordpress-backup

# Launch Admin Manager
./configure.sh --add-admin
```

This utility allows you to **List**, **Add**, and **Modify** admins (reset passwords).
