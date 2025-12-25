# Cloudflare D1 Integration

The backup system synchronizes logs with Cloudflare D1 for centralized tracking across multiple deployments.

## Configuration

Set D1 credentials in `.env` or via wizard:

```bash
./configure.sh --env
# Select option 2: Configure Global Credentials
```

### Required Variables

| Variable | Description |
|----------|-------------|
| `CLOUDFLARE_ACCOUNT_ID` | Your Cloudflare account ID |
| `CLOUDFLARE_API_TOKEN` | API token with D1 permissions |
| `CLOUDFLARE_D1_DATABASE_ID` | Target D1 database UUID |

### Creating API Token

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
2. Create token with permissions:
   - **Account** → D1 → Edit
3. Copy the token to `.env`

### Finding Database ID

```bash
# Using Wrangler
npx wrangler d1 list
```

Or find it in Cloudflare Dashboard → Workers & Pages → D1.

## Manual Sync

```bash
./run.sh --db-sync
```

Or directly:
```bash
./venv/bin/python3 lib/d1_manager.py
```

## Sync Behavior

### Push (Local → Remote)
- Compares local and remote IDs
- Batches new records (respects 100-parameter limit)
- Logs: `[D1] Pushing X records to remote in batches of Y...`

### Pull (Remote → Local)
- Identifies records missing locally
- Fetches in batches of 90
- Inserts into local SQLite

## Free Tier Optimization

The sync engine is designed for Cloudflare's free tier limits:

| Limit | Our Approach |
|-------|--------------|
| 100 parameters per query | Batch inserts: `90 / column_count` rows |
| 50 queries per invocation | Minimize by batching |
| 500 MB database | Only sync essential tables |

## Database Schema

### `backup_log`
```sql
CREATE TABLE backup_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    status TEXT,
    details TEXT,
    site_name TEXT,
    server_id TEXT
);
```

### `s3_archives`
```sql
CREATE TABLE s3_archives (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    s3_endpoint TEXT,
    s3_bucket TEXT,
    file_size INTEGER,
    upload_timestamp DATETIME,
    site_name TEXT,
    server_id TEXT
);
```

### `daily_emails`
```sql
CREATE TABLE daily_emails (
    id INTEGER PRIMARY KEY,
    date TEXT,
    email_sent INTEGER,
    backup_count INTEGER,
    server_id TEXT
);
```

## Schema Migration

When syncing, if `server_id` column is missing:
- Local: `ALTER TABLE` is executed automatically
- Remote: `ALTER TABLE` sent via API

No manual migration needed.

## Disabling D1

Leave `CLOUDFLARE_*` variables empty in `.env`. The sync will be skipped silently.

## Troubleshooting

### "D1 API Error"
- Check API token permissions
- Verify database ID is correct
- Ensure account ID matches

### "Sync failed"
- Run with DEBUG: `./venv/bin/python3 lib/d1_manager.py`
- Check network connectivity
- Verify D1 database exists

### Viewing D1 Data

```bash
# Using Wrangler
npx wrangler d1 execute YOUR_DB --command "SELECT * FROM backup_log LIMIT 10"
```
