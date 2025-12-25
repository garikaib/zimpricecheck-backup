# S3 Storage Configuration

The system supports **unlimited** S3-compatible storage servers (AWS S3, iDrive E2, Backblaze B2, DigitalOcean Spaces, MinIO, etc.).

Configuration is managed in `config.json`.

## Configuration Format

Servers are defined in the `storage` array. Each server has a `weight` that determines priority (higher = tried first).

```json
{
  "storage": [
    {
      "name": "idrive-primary",
      "type": "s3",
      "endpoint": "t5k4.ldn.idrivee2-61.com",
      "region": "eu-west-3",
      "access_key": "YOUR_ACCESS_KEY",
      "secret_key": "YOUR_SECRET_KEY",
      "bucket": "wordpress-backups",
      "weight": 100,
      "storage_limit_gb": 100
    },
    {
      "name": "aws-backup",
      "type": "s3",
      "endpoint": "s3.amazonaws.com",
      "region": "us-east-1",
      "access_key": "YOUR_AWS_KEY",
      "secret_key": "YOUR_AWS_SECRET",
      "bucket": "offsite-archive",
      "weight": 50,
      "storage_limit_gb": 500
    }
  ]
}
```

### Fields

| Field | Description | Required | Default |
|-------|-------------|----------|---------|
| `name` | Friendly name for logs | Yes | - |
| `type` | Must be `s3` | Yes | `s3` |
| `endpoint` | S3 API endpoint (no https://) | Yes | - |
| `region` | Region code | Yes | `us-east-1` |
| `bucket` | Bucket name | Yes | - |
| `weight` | Priority (1-100) | No | 100 |
| `storage_limit_gb` | Max usage before failover | No | 100 |

## Failover Behavior

1. The system sorts all configured servers by **Weight** (Descending).
2. It checks the first server:
   - Is it reachable?
   - Does it have free space (based on `storage_limit_gb`)?
3. If successful, upload proceeds.
4. If failed or full, it tries the next server in the list.
5. If all servers fail, the backup job is marked as `ERROR`.

## Provider Guides

### iDrive E2
- **Endpoint**: Find in specific bucket settings (e.g., `t5k4.ldn.idrivee2-61.com`)
- **Region**: e.g., `eu-west-3` (Paris)

### AWS S3
- **Endpoint**: `s3.amazonaws.com`
- **Region**: e.g., `us-east-1`

### Backblaze B2
- **Endpoint**: `s3.us-west-004.backblazeb2.com`
- **Region**: `us-west-004` (check local code)

### DigitalOcean Spaces
- **Endpoint**: `nyc3.digitaloceanspaces.com`
- **Region**: `nyc3`

## Testing

Run the S3 manager directly to test connectivity to all configured servers:

```bash
./venv/bin/python3 lib/s3_manager.py
```
