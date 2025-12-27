# Storage Providers & S3

The SaaS platform uses a **Centralized Storage Architecture**. Storage Providers are configured on the Master Server and shared across Nodes (or assigned to specific Nodes/Tenants in future, currently global default).

## key Concepts

1.  **Centralized Configuration**: Managed via Master API, not local `config.json`.
2.  **Encryption**: Access Keys and Secret Keys are stored **encrypted** in the database using `Fernet` (symmetric encryption).
3.  **Dynamic Provisioning**: Nodes request storage credentials from the Master only when needed (Zero Trust principle).
4.  **Reconciliation**: The Master periodically checks S3 buckets to sync usage data with the database (Drift Detection).

## Supported Providers

Any S3-compatible provider is supported:
- **iDrive E2** (Recommended/Default)
- **AWS S3**
- **Backblaze B2**
- **DigitalOcean Spaces**
- **MinIO** (Self-hosted)

## Managing Providers

Providers are managed by **Super Admins** via the API.

### 1. Create a Provider

```bash
POST /api/v1/storage/providers
{
  "name": "iDrive E2 Primary",
  "type": "s3",
  "endpoint": "t5k4.ldn.idrivee2-61.com",
  "bucket": "backups-bucket",
  "region": "eu-west-3",
  "access_key": "YOUR_ACCESS_KEY",
  "secret_key": "YOUR_SECRET_KEY",
  "storage_limit_gb": 1000,
  "is_default": true
}
```

### 2. Set Default

Only one provider can be `is_default=true` at a time. Setting a new default automatically unsets the previous one.

### 3. Usage & Quotas

Each provider tracks `used_gb` against `storage_limit_gb`.
- **Soft Limit**: Usage is tracked but uploads aren't Hard-Blocked by the *provider* logic (yet).
- **Hard Limit**: Nodes check Site/Node quotas before uploading.

### 4. Reconciliation

To fix discrepancies between the Database and actual S3 usage:

```bash
POST /api/v1/storage/reconcile?dry_run=false
```

This scans all active S3 paths known to the DB and updates `storage_used_bytes`.

## Directory Structure (S3)

Backups are stored using opaque UUIDs to prevent enumeration attacks and ensure uniqueness:

```
s3://<bucket>/<node_uuid>/<site_uuid>/<filename>.tar.zst
```

Example:
`s3://backups/3d298266-633b-48b6-9662-07a1d9ee1c44/a840cad8-9322-4ed1-a2ea-f65b1b14afa7/site.com_20251227_082133.tar.zst`

## Legacy Config (Deprecated)

The local `config.json` `storage` array is **deprecated** and ignored in Node Mode. It is only used for `standalone` local testing if explicitly invoked.
