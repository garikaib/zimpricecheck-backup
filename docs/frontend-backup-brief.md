# Frontend Backup System Integration

## Overview

The backup system provides real-time backup control with granular progress visibility. All backup progress is stored in the database, enabling multi-user visibility (e.g., Super Admin can see backups started by Site Admin).

---

## API Endpoints

### Start Backup
```
POST /api/v1/sites/{id}/backup/start
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "message": "Backup started for example.com",
  "status": "running",
  "site_id": 1
}
```

---

### Get Backup Status
```
GET /api/v1/sites/{id}/backup/status
Authorization: Bearer <token>
```

**Response:**
```json
{
  "site_id": 1,
  "site_name": "example.com",
  "status": "running",
  "progress": 40,
  "message": "Stage 2/5: backup_files",
  "stage": "backup_files",
  "stage_detail": "Files backed up (2048.5 MB)",
  "bytes_processed": 2147483648,
  "bytes_total": 5368709120,
  "error": null,
  "started_at": "2025-12-28T07:50:47.725070"
}
```

**Possible `status` values:**
| Status | Description |
|--------|-------------|
| `idle` | No backup running |
| `running` | Backup in progress |
| `completed` | Backup finished successfully |
| `failed` | Backup failed (check `error` field) |
| `stopped` | User stopped the backup |

**Stages (in order):**
1. `backup_db` - Dumping MySQL database
2. `backup_files` - Copying wp-content
3. `create_bundle` - Creating tar.zst archive
4. `upload_remote` - Uploading to S3 storage
5. `cleanup` - Removing temp files

---

### Stop Backup
```
POST /api/v1/sites/{id}/backup/stop
Authorization: Bearer <token>
```

---

### Reset Stuck Backup
```
POST /api/v1/daemon/backup/reset/{id}
Authorization: Bearer <token>
```
Use when backup is stuck in "running" state.

---

### SSE Progress Stream
```
GET /api/v1/daemon/backup/stream/{id}?token=<jwt>&interval=2
```

**JavaScript Example:**
```javascript
const token = 'your-jwt-token';
const source = new EventSource(
  `/api/v1/daemon/backup/stream/${siteId}?token=${token}&interval=2`
);

source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.status}] ${data.progress}% - ${data.stage_detail}`);
  
  if (['completed', 'failed', 'stopped'].includes(data.status)) {
    source.close();
  }
};

source.onerror = () => source.close();
```

---

## UI Implementation Guide

### Backup Button States

```
┌─────────────────────────────────────────┐
│ Site: example.com                       │
├─────────────────────────────────────────┤
│ [Start Backup]  ← idle state            │
│                                         │
│ ████████░░░░░░░░ 40%                    │
│ Stage: backup_files                     │
│ Detail: Files backed up (2048.5 MB)     │
│ [Stop]                                  │
│                                         │
│ ✓ Backup completed                      │
│ [Download] [Start New]                  │
│                                         │
│ ✗ Backup failed: Upload error           │
│ [Retry] [View Logs]                     │
└─────────────────────────────────────────┘
```

### Polling vs SSE

| Method | When to Use |
|--------|-------------|
| **Polling** | Simple implementation, works everywhere |
| **SSE** | Real-time updates, lower latency |

**Recommended polling interval:** 2-5 seconds during active backup.

---

## Multi-User Visibility

Progress is stored in the **database**, so all users with site access see the same status:
- Site Admin starts backup
- Super Admin sees progress in real-time
- Node Admin sees all backups on their nodes

No special handling needed - just query the same status endpoint.

---

## Error Handling

```javascript
try {
  await startBackup(siteId);
} catch (error) {
  if (error.status === 409) {
    // Backup already running
    showToast('A backup is already in progress');
  } else if (error.status === 403) {
    // Access denied
    showToast('You do not have permission to backup this site');
  }
}
```

---

## TypeScript Types

```typescript
interface BackupStatus {
  site_id: number;
  site_name: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'stopped';
  progress: number;  // 0-100
  message: string;
  stage: string | null;
  stage_detail: string | null;
  bytes_processed: number;
  bytes_total: number;
  error: string | null;
  started_at: string | null;  // ISO datetime
}
```
