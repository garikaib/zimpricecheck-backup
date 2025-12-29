# Frontend Brief: Unified Node Stats Streaming

## Overview
The backend now provides a **single SSE endpoint** that streams real-time statistics for **all nodes** (Master + Remote) in one unified format. This replaces the need to manage separate data sources.

## New Endpoints

### Primary: `GET /api/v1/metrics/nodes/stats/stream`
Streams stats for **ALL** active nodes in a single unified format.

### Per-Node: `GET /api/v1/metrics/nodes/{node_id}/stats/stream`
Streams stats for a **single** node (useful for node detail modals).

## SSE Connection Example

```typescript
// composables/useNodeStats.ts
export function useNodeStats(interval = 5) {
  const nodes = ref<NodeStats[]>([])
  const connected = ref(false)
  
  const { token } = useAuth()
  
  onMounted(() => {
    const url = `/api/v1/metrics/nodes/stats/stream?token=${token.value}&interval=${interval}`
    const source = new EventSource(url)
    
    source.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.event === 'connected') {
        connected.value = true
        return
      }
      nodes.value = data.nodes
    }
    
    source.onerror = () => {
      connected.value = false
    }
    
    onUnmounted(() => source.close())
  })
  
  return { nodes, connected }
}
```

## Response Format

Each SSE event contains:

```json
{
  "timestamp": "2025-12-29T07:00:00Z",
  "nodes": [
    {
      "id": 2,
      "hostname": "api.zimpricecheck.com",
      "status": "online",         // online | stale | offline
      "is_master": false,
      "cpu_percent": 12,
      "memory_percent": null,     // null for remote nodes (not tracked)
      "disk_percent": 51,
      "uptime_seconds": null,     // null for remote nodes
      "active_backups": 0,
      "last_seen": "2025-12-29T06:59:30Z"
    },
    {
      "id": 3,
      "hostname": "wp.zimpricecheck.com",
      "status": "online",
      "is_master": true,
      "cpu_percent": 5.0,
      "memory_percent": 72.8,     // Available for master
      "disk_percent": 51.5,
      "uptime_seconds": 447000,   // Available for master
      "active_backups": 1,
      "last_seen": null           // null for master (always live)
    }
  ]
}
```

## Node Status Badges

| Status | Badge Color | Description |
|--------|-------------|-------------|
| `online` | Green | Node actively reporting |
| `stale` | Yellow | No stats in >5 minutes |
| `offline` | Red | Never reported stats |

## Dashboard Integration

```vue
<template>
  <div class="grid grid-cols-2 gap-4">
    <NodeCard
      v-for="node in nodes"
      :key="node.id"
      :node="node"
    />
  </div>
</template>

<script setup>
const { nodes } = useNodeStats(5) // Poll every 5 seconds
</script>
```

## Key Differences from Previous API

| Aspect | Old (`/metrics/node/stream`) | New (`/metrics/nodes/stats/stream`) |
|--------|------------------------------|-------------------------------------|
| Scope | Master only | All nodes |
| Data source | Local psutil | Master: psutil, Remote: DB |
| Format | Full metrics blob | Simplified, unified |
| Use case | Single server monitoring | Cluster dashboard |

## Backward Compatibility
The old endpoints (`/metrics/node/stream`, `/nodes/`) remain functional. The new unified stream is **additive**.
