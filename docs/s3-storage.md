# S3-Compatible Storage

The backup system supports **unlimited S3-compatible storage servers**. This includes:

- **AWS S3**
- **iDrive E2**
- **Backblaze B2**
- **Wasabi**
- **MinIO**
- **DigitalOcean Spaces**
- Any S3-compatible provider

## Configuration

### Adding S3 Servers

S3 servers are configured via environment variables in `.env`. You can add as many servers as needed using numbered prefixes:

```env
# Server 1: iDrive E2 (Primary)
S3_SERVER_1_ENDPOINT="t5k4.ldn.idrivee2-61.com"
S3_SERVER_1_REGION="eu-west-3"
S3_SERVER_1_ACCESS_KEY="your-access-key"
S3_SERVER_1_SECRET_KEY="your-secret-key"
S3_SERVER_1_BUCKET="wordpress-backups"
S3_SERVER_1_STORAGE_LIMIT_GB="100"

# Server 2: AWS S3 (Backup)
S3_SERVER_2_ENDPOINT="s3.amazonaws.com"
S3_SERVER_2_REGION="us-east-1"
S3_SERVER_2_ACCESS_KEY="AKIA..."
S3_SERVER_2_SECRET_KEY="..."
S3_SERVER_2_BUCKET="my-wp-backups"
S3_SERVER_2_STORAGE_LIMIT_GB="500"

# Server 3: Backblaze B2 (Archive)
S3_SERVER_3_ENDPOINT="s3.us-west-004.backblazeb2.com"
S3_SERVER_3_REGION="us-west-004"
S3_SERVER_3_ACCESS_KEY="..."
S3_SERVER_3_SECRET_KEY="..."
S3_SERVER_3_BUCKET="long-term-backups"
S3_SERVER_3_STORAGE_LIMIT_GB="1000"
```

### Configuration Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `S3_SERVER_N_ENDPOINT` | S3 endpoint hostname | Yes |
| `S3_SERVER_N_REGION` | AWS region code | Yes |
| `S3_SERVER_N_ACCESS_KEY` | Access key ID | Yes |
| `S3_SERVER_N_SECRET_KEY` | Secret access key | Yes |
| `S3_SERVER_N_BUCKET` | Bucket name | Yes |
| `S3_SERVER_N_STORAGE_LIMIT_GB` | Max storage to use (GB) | No (default: 100) |

### Interactive Setup

Run the configuration wizard to add S3 servers interactively:

```bash
./configure.sh
```

Select "S3 Storage" when prompted.

## How It Works

### Upload Process

1. Backup manager creates archive locally
2. S3 manager tries each configured server in order (1, 2, 3...)
3. First server with enough space receives the upload
4. Upload recorded in `s3_archives` table

### Folder Structure

Archives are stored with this path:

```
/{SERVER_ID}/{Year}/{Month}/{Day}/{filename}.tar.zst
```

Example:
```
/wp-server-1/2024/12/25/zimpricecheck-backup-20241225-083000.tar.zst
```

This structure:
- Prevents conflicts when multiple servers share storage
- Enables easy browsing by date
- Supports retention policies

### Failover

If a server fails or runs out of space:
1. Error is logged
2. Next server is tried
3. Process continues until success or all servers fail

## Provider-Specific Setup

### iDrive E2

1. Log in to [iDrive E2 Console](https://www.idrive.com/e2/)
2. Create a new bucket
3. Go to **Access Keys** and create a new key
4. Note your endpoint (e.g., `t5k4.ldn.idrivee2-61.com`)
5. Use region code from the console (e.g., `eu-west-3`)

```env
S3_SERVER_1_ENDPOINT="t5k4.ldn.idrivee2-61.com"
S3_SERVER_1_REGION="eu-west-3"
S3_SERVER_1_ACCESS_KEY="GsnM5f..."
S3_SERVER_1_SECRET_KEY="jgQD20..."
S3_SERVER_1_BUCKET="wordpress-backups"
```

### AWS S3

1. Create an S3 bucket in AWS Console
2. Create an IAM user with S3 access
3. Generate access keys for the user

```env
S3_SERVER_1_ENDPOINT="s3.amazonaws.com"
S3_SERVER_1_REGION="us-east-1"
S3_SERVER_1_ACCESS_KEY="AKIAIOSFODNN7EXAMPLE"
S3_SERVER_1_SECRET_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
S3_SERVER_1_BUCKET="my-wordpress-backups"
```

### Backblaze B2

1. Create a B2 bucket
2. Create an application key with read/write access
3. Use the S3-compatible endpoint

```env
S3_SERVER_1_ENDPOINT="s3.us-west-004.backblazeb2.com"
S3_SERVER_1_REGION="us-west-004"
S3_SERVER_1_ACCESS_KEY="your-key-id"
S3_SERVER_1_SECRET_KEY="your-application-key"
S3_SERVER_1_BUCKET="wordpress-backups"
```

### DigitalOcean Spaces

```env
S3_SERVER_1_ENDPOINT="nyc3.digitaloceanspaces.com"
S3_SERVER_1_REGION="nyc3"
S3_SERVER_1_ACCESS_KEY="..."
S3_SERVER_1_SECRET_KEY="..."
S3_SERVER_1_BUCKET="my-backups"
```

## Testing

Verify S3 connectivity:

```bash
./venv/bin/python3 lib/s3_manager.py
```

Expected output:
```
Configured S3 servers: 1
  - S3Server(1: t5k4.ldn.idrivee2-61.com/wordpress-backups)
    Usage: 0.00 MB
```

## Troubleshooting

### "No S3 servers configured"

Ensure at least `S3_SERVER_1_ENDPOINT` is set in `.env`.

### "Invalid S3 credentials"

- Verify access key and secret key are correct
- Check that the key has read/write permissions to the bucket
- Ensure the bucket name is correct

### "Not enough space"

- Increase `S3_SERVER_N_STORAGE_LIMIT_GB`
- Add another S3 server as overflow
- Enable retention cleanup

### Connection Errors

- Verify endpoint URL is correct (no `https://` prefix)
- Check region code matches the bucket location
- Ensure firewall allows outbound HTTPS (port 443)
