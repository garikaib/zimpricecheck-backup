# Frontend Implementation Brief: Backup Scheduling

## Overview
Users can now schedule automated backups for their sites.
This feature should be exposed in the **Site Details** modal or page, under a new "Settings" or "Schedule" tab.

## API Endpoint
**Update Schedule**: `PUT /sites/{id}/schedule`

## UI Requirements

### 1. Schedule Configuration Form
Fields:
- **Frequency**: Dropdown [`Manual` (default), `Daily`, `Weekly`, `Monthly`]
- **Time**: Time Picker (HH:MM). Label must state: **"Time (Africa/Harare)"**.
- **Days**:
  - If `Daily`: Hidden.
  - If `Weekly`: Multi-select checkboxes [Mon, Tue, Wed, Thu, Fri, Sat, Sun]. Send as CSV (0=Mon, 6=Sun).
  - If `Monthly`: Number input (1-31). Send as CSV (e.g. "1" or "1,15").
- **Retention**: Number Input. Label: "Retention Copies". Default `5`. Max `10`.

### 2. Data Handling
Payload Example:
```json
{
  "schedule_frequency": "weekly",
  "schedule_time": "23:00",
  "schedule_days": "0,2,4", // Mon, Wed, Fri
  "retention_copies": 7
}
```

### 3. State Management
- When opening the form, populate with existing values from `site` object fields:
  - `site.schedule_frequency`
  - `site.schedule_time`
  - `site.schedule_days`
  - `site.retention_copies`
- If `frequency` is "manual", hide Time/Days fields.

### 4. Display Info
- Show `site.next_run_at` in the UI (e.g., "Next Backup: Dec 28, 23:00 (Harare)").
- Status Badges: Show "Scheduled" vs "Manual".

## Validation Rules
- **Time**: Must be valid HH:MM.
- **Retention**: Must be positive integer (1-10 recommended).
