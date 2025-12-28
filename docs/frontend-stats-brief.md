# Frontend Brief: Node Statistics Display

## Overview
The backend has been updated to provide real-time CPU, Disk, and Backup activity statistics for all nodes (including remote nodes) via the main `/api/v1/nodes/` endpoint. This resolves the issue where Node Cards were displaying empty or placeholder data.

## API Changes

### `GET /api/v1/nodes/`
The node objects in the response list now include a `stats` field.

**Response Example:**
```json
[
  {
    "id": 2,
    "hostname": "api.zimpricecheck.com",
    "status": "active",
    "stats": [
      {
        "cpu_usage": 12,       // Percent (0-100)
        "disk_usage": 45,      // Percent (0-100)
        "active_backups": 1    // Number of currently running jobs
      }
    ]
  }
]
```

### `GET /api/v1/nodes/{id}`
The node detail endpoint also includes the `stats` field with the same structure.

## Frontend Implementation Guidelines

### 1. Dashboard / Node List
- **Source**: Continue using `useAsyncData` to fetch `/nodes/`. 
- **Mapping**: Map the `stats` array to your UI components.
  - **CPU**: `node.stats[0]?.cpu_usage ?? 0`
  - **Disk**: `node.stats[0]?.disk_usage ?? 0`
  - **Status**: `node.stats[0]?.active_backups > 0 ? 'Busy' : 'Idle'`
- **Fallback**: If `node.stats` is empty or undefined, the node usually hasn't reported in yet (or is offline). Display "N/A" or "Offline".

### 2. Node Detail Modal
- Use the same logic as above. The backend ensures that the `stats` list contains the most recent report (latest 1 entry).

### 3. Real-Time Updates
- **Master Node**: The existing `/metrics/node/stream` SSE still works for the Master server itself.
- **Remote Nodes**: Currently, remote nodes report stats via pulse (every 1 minute). To show "live" updates for remote nodes, simply polling `/nodes/` or `/nodes/{id}` every 30-60 seconds is sufficient.
- **Future**: We may implement an SSE aggregator for all nodes if higher frequency is required.

## Notes
- The backend automatically cleans up stats older than 10 minutes to prevent database bloat.
- The `node.stats` field is technically a list (to support future history), but currently typically contains 0 or 1 item (the latest). Always check for existence (`length > 0`) before accessing index 0.
