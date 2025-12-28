# Frontend Brief: Schedule Fields Now Available

## Summary
Schedule fields are **now included** in site list and detail API responses. The frontend scheduler modal should pre-populate with saved values.

---

## API Response Changes

### GET /sites/ (List)
Each site object in the response now includes:

```json
{
  "id": 1,
  "name": "example.com",
  "wp_path": "/var/www/example/htdocs",
  "schedule_frequency": "daily",
  "schedule_time": "02:00",
  "schedule_days": "0,2,4",
  "retention_copies": 7,
  "next_run_at": "2025-12-29T00:00:00"
}
```

### GET /sites/{id} (Detail)
Same fields available on individual site response.

---

## Frontend Integration

### When Opening Scheduler Modal

```typescript
// Pre-populate form with existing values
const site = await fetchSite(siteId);

form.frequency = site.schedule_frequency || 'manual';
form.time = site.schedule_time || '02:00';
form.days = site.schedule_days?.split(',') || [];
form.retention = site.retention_copies || 5;
```

### TypeScript Interface Update

```typescript
interface Site {
  id: number;
  name: string;
  // ... existing fields
  
  // Schedule fields
  schedule_frequency: 'manual' | 'daily' | 'weekly' | 'monthly';
  schedule_time: string | null;
  schedule_days: string | null;  // CSV: "0,2,4"
  retention_copies: number;
  next_run_at: string | null;    // ISO datetime
}
```

---

## UI Display

| Field | Display |
|-------|---------|
| `schedule_frequency` | Badge: "Manual" / "Daily" / "Weekly" / "Monthly" |
| `schedule_time` | "Scheduled at 02:00 (Harare)" |
| `next_run_at` | "Next backup: Dec 29, 2025 00:00" |
| `retention_copies` | "Keeping 7 copies" |

---

## Save Endpoint (unchanged)

```
PUT /sites/{id}/schedule
```

```json
{
  "schedule_frequency": "weekly",
  "schedule_time": "03:00",
  "schedule_days": "1,3,5",
  "retention_copies": 5
}
```

---

## Checklist

- [ ] Update `Site` TypeScript interface with new fields
- [ ] Pre-populate scheduler modal form from site data
- [ ] Display schedule info in site list/cards
- [ ] Show "Next backup" when `next_run_at` is set
