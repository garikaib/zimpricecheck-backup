# User Management & Roles

For API details, see [Users API Reference](api/users.md).

## Role Hierarchy

The platform uses a role-based access control (RBAC) system with three levels:

### 1. Super Admin (`super_admin`)
- **Scope**: Global.
- **Capabilities**:
    - Deploy and approve new Nodes.
    - Manage Storage Providers.
    - View/Edit/Delete any User, Site, or Backup.
    - Trigger global cleanup/updates.

### 2. Node Admin (`node_admin`)
- **Scope**: Assigned Nodes.
- **Capabilities**:
    - View details of their Nodes.
    - Manage Sites on their Nodes.
    - View Backups for their Sites.
    - Create `site_admin` users (future feature).
    - Cannot modify Storage Providers.

### 3. Site Admin (`site_admin`)
- **Scope**: Assigned Sites.
- **Capabilities**:
    - View their Sites.
    - View/Download Backups.
    - Trigger Manual Backups.
    - Cannot see infrastructure details (Node stats, Storage config).

## Management

Users are currently managed via the API or Dashboard by Super Admins.
