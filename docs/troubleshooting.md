# Troubleshooting

## Service Names

| Component | Service Name | Logs |
|-----------|--------------|------|
| **Node Agent** | `wordpress-backup-daemon` | `journalctl -u wordpress-backup-daemon` |
| **Master Server** | `wordpress-master` | `journalctl -u wordpress-master` |

## Common Issues

### 1. Node Not Registering
**Symptom**: Node deployed but doesn't appear in Master "Pending Nodes".

**Check**:
1. SSH into Node: `ssh ubuntu@<node-ip>`
2. Check logs: `sudo journalctl -u wordpress-backup-daemon -f`
   - Should see: `[Scanning] Found X compatible sites`
   - Should see: `[Registration] Code generated: XXXXX`

**Fix**:
- Ensure `MASTER_URL` in `.env` is correct.
- Ensure Node can reach Master (firewall/security groups).
- If "Already registered", check `config.json` for cached UUID.

### 2. Backup Fails (Quota Exceeded)
**Symptom**: Backup job marked as `SKIPPED` or `FAILED` with "Quota Exceeded".

**Check**:
- Check Master Dashboard > Site > Quota.
- Run pre-check manually: `curl ... /sites/{id}/quota/check`

**Fix**:
- Delete old backups (`DELETE /backups/{id}`).
- Increase Site or Node quota (`PUT /sites/{id}/quota`).
- Clean up S3 manually if drift occurred (then `POST /storage/reconcile`).

### 3. S3 Upload Failed
**Symptom**: `ClientError: An error occurred (403)`.

**Check**:
- Verify Storage Provider Config on Master.
- Check if S3 credentials are valid.
- Check time sync on Node (S3 auth fails if clock skewed): `date`.

**Fix**:
- Update credentials in Master Dashboard.
- `sudo ntpdate pool.ntp.org` on Node.

### 4. 500 Internal Server Error (Master)
**Symptom**: API returns 500.

**Check**:
- Master logs: `ssh ubuntu@<master-ip> "sudo journalctl -u wordpress-master -n 50"`
- Search for Python Traceback.

**Fix**:
- Report bug with traceback.
- Restart service: `sudo systemctl restart wordpress-master`.

### 5. "Permission Denied" (Node)
**Symptom**: Daemon can't read `wp-config.php` or write temp files.

**Check**:
- Service runs as `root` (usually) or a user with correct groups?
- Agent runs as root by default to access `/var/www` owned by `www-data`.

**Fix**:
- Ensure daemon running as root or has `sudo` capability (less secure, but often necessary for `/var/www` access).

## Diagnostic Commands (Node)

```bash
# Check Daemon Status
sudo systemctl status wordpress-backup-daemon

# Run Manual Scan
sudo /opt/wordpress-backup/venv/bin/python3 -m daemon.main --scan

# Run Manual Backup for Site ID 1
sudo /opt/wordpress-backup/venv/bin/python3 -m daemon.module --backup 1
```

## Resetting State

If a Node is "stuck" or you want to register it as a new node:

```bash
# On Node
sudo systemctl stop wordpress-backup-daemon
rm /etc/backupd/config.json  # Delete identity
rm /etc/backupd/uuid         # Delete UUID
sudo systemctl start wordpress-backup-daemon
```

### 6. Communication Channel Test Fails

**Symptom**: `POST /communications/channels/{id}/test` returns error like "Failed to decrypt channel config" or "Invalid config".

**Check**:
1. Check if `SECRET_KEY` in `.env` matches what was used when the channel was created.
2. Verify the channel has all required config fields via `GET /communications/providers`.

**Fix**:
- Re-save the channel configuration with all required fields via `PUT /communications/channels/{id}`.
- See [Communications API Troubleshooting](api/communications.md#troubleshooting) for details.

