# User Management & Roles

For API details, see [Users API Reference](api/users.md).
For frontend implementation, see [Frontend RBAC Brief](frontend-rbac-brief.md).

## Role Hierarchy

The platform uses a role-based access control (RBAC) system with three levels:

### 1. Super Admin (`super_admin`)
- **Scope**: Global.
- **Capabilities**:
    - Deploy and approve new Nodes.
    - Manage Storage Providers.
    - View/Edit/Delete any User, Site, or Backup.
    - Assign Nodes to Node Admins.
    - Assign Sites to Site Admins.
    - Trigger global cleanup/updates.

### 2. Node Admin (`node_admin`)
- **Scope**: Assigned Nodes only.
- **Capabilities**:
    - View details of their assigned Nodes.
    - Manage Sites on their assigned Nodes.
    - View/Manage Backups for Sites on their Nodes.
    - View Site Admins managing sites on their nodes.
    - Cannot modify Storage Providers or other Nodes.

### 3. Site Admin (`site_admin`)
- **Scope**: Assigned Sites only.
- **Capabilities**:
    - View their assigned Sites.
    - Start/Stop/View Status of Backups for their Sites.
    - View/Download Backups.
    - Cannot see infrastructure details (Node stats, Storage config).

## Assignment Model

Users are assigned to resources via Many-to-Many relationships:

| Role | Assignment Field | Managed By |
|------|------------------|------------|
| Node Admin | `assigned_nodes` | Super Admin |
| Site Admin | `assigned_sites` | Super Admin |

### Assignment Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /users/{id}/nodes` | POST | Assign nodes to user |
| `POST /users/{id}/sites` | POST | Assign sites to user |
| `DELETE /users/{id}/nodes/{node_id}` | DELETE | Remove node assignment |
| `DELETE /users/{id}/sites/{site_id}` | DELETE | Remove site assignment |

## Management

Users are managed via the API or Dashboard by Super Admins.

