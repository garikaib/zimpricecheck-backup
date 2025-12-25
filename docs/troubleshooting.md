# Troubleshooting

## Common Issues

### Backup Not Running

**Symptom**: Timer enabled but backups don't execute.

**Check**:
```bash
# Timer status
systemctl status wordpress-backup.timer

# Service logs
journalctl -u wordpress-backup.service -n 50

# Manual test
cd /opt/wordpress-backup
./run.sh -f
```

**Solutions**:
- Ensure `sites.json` exists and has sites defined
- Check Python venv: `./venv/bin/python3 --version`
- Verify file permissions: `ls -la`

---

### "No sites.json found"

**Symptom**: Backup exits immediately with this message.

**Solution**:
```bash
./configure.sh --sites
# Add at least one site
```

---

### Database Backup Failed

**Symptom**: `mysqldump failed` error.

**Check**:
```bash
# Test credentials manually
mysqldump --host=localhost --user=USER --password=PASS DATABASE > /dev/null
```

**Solutions**:
- Verify DB credentials in `sites.json`
- Ensure `mysqldump` is installed: `which mysqldump`
- Check if database exists
- Try auto-extraction (leave DB fields blank in site config)

---

### S3 Upload Failed

**Symptom**: Backup created but not uploaded.

**Check**:
```bash
# Test S3 connectivity
./venv/bin/python3 lib/s3_manager.py
```

**Solutions**:
- Verify S3 credentials in `.env` (`S3_SERVER_1_*` variables)
- Check endpoint URL is correct (no `https://` prefix)
- Ensure bucket exists or will be auto-created
- Verify network allows outbound HTTPS (port 443)
- Check storage limit: increase `S3_SERVER_1_STORAGE_LIMIT_GB`

---

### D1 Sync Failed

**Symptom**: `[D1] Sync failed` or API errors.

**Check**:
```bash
# Test manually
./venv/bin/python3 lib/d1_manager.py
```

**Solutions**:
- Verify `CLOUDFLARE_*` variables in `.env`
- Check API token permissions (D1 Edit)
- Ensure database ID is correct
- Test network: `curl https://api.cloudflare.com`

---

### Permission Denied

**Symptom**: Various "Permission denied" errors.

**Solutions**:
```bash
# Fix ownership
sudo chown -R ubuntu:ubuntu /opt/wordpress-backup

# Fix work directory
sudo chown -R ubuntu:ubuntu /var/tmp/wp-backup-work
sudo chmod 775 /var/tmp/wp-backup-work

# Fix scripts
chmod +x run.sh configure.sh deploy.sh
```

---

### Deploy Script Hangs

**Symptom**: `deploy.sh` stalls during upload or setup.

**Solutions**:
- Check SSH key: `ssh -p PORT user@host`
- Verify port in `.env`: `REMOTE_PORT`
- Test connectivity: `ping REMOTE_HOST`
- Try with verbose: `bash -x deploy.sh`

---

### "Another backup is running"

**Symptom**: Script exits saying backup already in progress.

**Check**:
```bash
# Is it actually running?
ps aux | grep backup_manager

# Check lock file
ls -la /var/tmp/wp-backup.pid
cat /var/tmp/wp-backup.pid
```

**Solution** (if stale):
```bash
rm /var/tmp/wp-backup.pid
rm /var/tmp/wp-backup.status
```

---

### Email Not Sending

**Symptom**: No email notifications received.

**Check**:
```bash
# View logs
journalctl -u wordpress-report.service -n 50
```

**Solutions**:
- Verify SMTP credentials in `.env`
- Check SMTP server allows your IP
- For Gmail: Use App Password, not account password
- Test: `./venv/bin/python3 lib/report_manager.py`

---

## Viewing Logs

### Systemd Logs
```bash
# Backup service
journalctl -u wordpress-backup.service -f

# Report service
journalctl -u wordpress-report.service -f
```

### Database Logs
```bash
sqlite3 /opt/wordpress-backup/backups.db \
  "SELECT * FROM backup_log ORDER BY timestamp DESC LIMIT 20;"
```

### Timer Schedule
```bash
systemctl list-timers --all | grep wordpress
```

## Getting Help

If issues persist:
1. Check GitHub Issues
2. Run backup with `-f` flag for full output
3. Collect logs: `journalctl -u wordpress-backup.service > debug.log`
