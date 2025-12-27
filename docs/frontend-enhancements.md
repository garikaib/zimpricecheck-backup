# Frontend Enhancement Brief

Comprehensive guide for frontend enhancements to the WordPress Backup SaaS dashboard.

---

## Part 1: Quota & Storage Visualization

### 1.1 Quota Progress Bars

**Priority: HIGH**

Display visual quota usage for sites and nodes.

**API Endpoints:**
- `GET /sites/{id}/quota/status`
- `GET /nodes/{id}/quota/status`

**UI Components Needed:**
```
┌─────────────────────────────────────────────────┐
│ Site: example.com                               │
│ ████████░░░░░░░░░░░░░░░░░░░░░░░  22.4%         │
│ 3.36 GB / 15 GB                                │
└─────────────────────────────────────────────────┘
```

**Color Coding:**
- Green: 0-79%
- Yellow: 80-99%
- Red: 100%+

**Implementation:**
```javascript
// Fetch quota status
const quotaStatus = await api.get(`/sites/${siteId}/quota/status`)

// Display progress bar
<ProgressBar 
  value={quotaStatus.usage_percent}
  color={quotaStatus.is_over_quota ? 'red' : quotaStatus.usage_percent > 80 ? 'yellow' : 'green'}
  label={`${quotaStatus.used_gb} GB / ${quotaStatus.quota_gb} GB`}
/>
```

---

### 1.2 Storage Health Dashboard Widget

**Priority: HIGH**

Global health indicator on main dashboard.

**API Endpoint:** `GET /storage/health`

**UI Components:**
```
┌─────────────────────────────────────────────────┐
│ 💾 Storage Health                    ✅ Healthy │
│ Total Used: 12.5 GB                            │
│ Sites Over Quota: 0                            │
│ Pending Deletions: 0                           │
└─────────────────────────────────────────────────┘
```

**Alerts:**
- Show warning banner if `healthy: false`
- List `over_quota_sites` and `warning_sites`
- Badge count on sidebar nav

---

### 1.3 Scheduled Deletions Alert

**Priority: MEDIUM**

Show upcoming automatic backup deletions.

**API Endpoint:** `GET /backups/scheduled-deletions`

**UI Components:**
```
┌─────────────────────────────────────────────────┐
│ ⚠️ Scheduled Deletions                          │
├─────────────────────────────────────────────────┤
│ backup_2025-12-20.tar.gz                       │
│ Site: example.com                              │
│ Deletes in: 2 days  [Cancel] [Delete Now]      │
├─────────────────────────────────────────────────┤
│ backup_2025-12-18.tar.gz                       │
│ Site: other-site.com                           │
│ Deletes in: 3 days  [Cancel] [Delete Now]      │
└─────────────────────────────────────────────────┘
```

**Actions:**
- Cancel: `DELETE /backups/{id}/cancel-deletion`
- Delete Now: `DELETE /backups/{id}`

---

## Part 2: Pre-Backup Quota Check

### 2.1 Backup Button Enhancement

**Priority: HIGH**

Check quota before starting backup.

**API Endpoint:** `GET /sites/{id}/quota/check`

**Flow:**
1. User clicks "Start Backup"
2. Call quota check endpoint
3. If `can_proceed: false`, show warning dialog
4. Allow override or cancel

**Dialog:**
```
┌─────────────────────────────────────────────────┐
│ ⚠️ Quota Warning                                │
├─────────────────────────────────────────────────┤
│ This backup would exceed your quota.           │
│                                                │
│ Current: 13.5 GB / 15 GB                       │
│ Estimated: +3.5 GB                             │
│ Projected: 17.0 GB (over by 2 GB)              │
│                                                │
│ Options:                                       │
│ • Delete old backups first                     │
│ • Increase site quota                          │
│ • Proceed anyway (warning email sent)          │
│                                                │
│        [Cancel]        [Proceed Anyway]        │
└─────────────────────────────────────────────────┘
```

---

## Part 3: Quota Management UI

### 3.1 Site Quota Editor

**Priority: MEDIUM**

Allow editing site quota with validation feedback.

**API Endpoint:** `PUT /sites/{id}/quota?quota_gb=X`

**UI:**
```
┌─────────────────────────────────────────────────┐
│ Site Quota Settings                            │
├─────────────────────────────────────────────────┤
│ Current Quota: 15 GB                           │
│ Node Limit: 100 GB                             │
│ Available: 85 GB                               │
│                                                │
│ New Quota: [____20____] GB                     │
│                                                │
│ ✓ Valid (within node limit)                    │
│                                                │
│        [Cancel]        [Save]                  │
└─────────────────────────────────────────────────┘
```

**Validation:**
- Show error if exceeds node quota
- Show remaining node quota after update

---

### 3.2 Node Quota Breakdown

**Priority: MEDIUM**

Show how node quota is distributed across sites.

**API Endpoint:** `GET /nodes/{id}/quota/status`

**UI:**
```
┌─────────────────────────────────────────────────┐
│ Node: wp.zimpricecheck.com                     │
│ ████████░░░░░░░░░░░░░░░░░░░░░░░  12.5%         │
│ 12.5 GB / 100 GB                               │
├─────────────────────────────────────────────────┤
│ Site Breakdown:                                │
│ example.com      ████░░░░░░  5.2/15 GB (34%)   │
│ blog.example.com ████░░░░░░  4.1/10 GB (41%)   │
│ shop.example.com ████████░░  3.2/4 GB (80%) ⚠️ │
└─────────────────────────────────────────────────┘
```

---

## Part 4: Security Enhancements

### 4.1 Session Management

**Priority: HIGH**

**Features:**
- [ ] Token refresh before expiry
- [ ] Auto-logout on inactivity
- [ ] Session list with revoke option
- [ ] Device tracking

**Implementation:**
```javascript
// Token refresh interceptor
api.interceptors.request.use(async (config) => {
  if (tokenExpiresSoon()) {
    await refreshToken()
  }
  return config
})
```

---

### 4.2 CSRF Protection

**Priority: HIGH**

**Features:**
- [ ] CSRF token in requests
- [ ] SameSite cookies
- [ ] Origin validation

---

### 4.3 Rate Limiting Indicators

**Priority: MEDIUM**

**Features:**
- [ ] Show remaining API calls
- [ ] Warn before hitting limit
- [ ] Retry with exponential backoff

---

### 4.4 Input Validation

**Priority: HIGH**

**Features:**
- [ ] Client-side validation matching backend
- [ ] XSS prevention on all inputs
- [ ] SQL injection prevention (backend)
- [ ] Path traversal prevention

---

## Part 5: Robustness Enhancements

### 5.1 Error Handling

**Priority: HIGH**

**Features:**
- [ ] Graceful error display
- [ ] Retry mechanisms for transient errors
- [ ] Offline detection and queue
- [ ] Error reporting to backend

**Error Component:**
```
┌─────────────────────────────────────────────────┐
│ ❌ Failed to load site quota                    │
│                                                │
│ Error: Network timeout                         │
│                                                │
│ [Retry]  [Report Issue]  [Dismiss]             │
└─────────────────────────────────────────────────┘
```

---

### 5.2 Loading States

**Priority: MEDIUM**

**Features:**
- [ ] Skeleton loaders for all data
- [ ] Progress indicators for long operations
- [ ] Optimistic updates where safe

---

### 5.3 Real-time Updates

**Priority: LOW**

**Features:**
- [ ] WebSocket for backup progress
- [ ] Auto-refresh quota after backup
- [ ] Live storage health updates

---

## Part 6: Accessibility & UX

### 6.1 Accessibility (a11y)

**Priority: MEDIUM**

**Features:**
- [ ] ARIA labels on all components
- [ ] Keyboard navigation
- [ ] Screen reader support
- [ ] Color contrast compliance

---

### 6.2 Responsive Design

**Priority: MEDIUM**

**Features:**
- [ ] Mobile-friendly quota displays
- [ ] Touch-friendly buttons
- [ ] Collapsible navigation

---

## Implementation Priority Order

| Phase | Features | Effort |
|-------|----------|--------|
| 1 | Quota progress bars, health widget | 2-3 days |
| 2 | Pre-backup check, scheduled deletions | 2 days |
| 3 | Quota editor, node breakdown | 2 days |
| 4 | Session management, error handling | 3 days |
| 5 | Real-time updates, accessibility | 4 days |

---

## API Endpoints Summary

| Feature | Endpoint | Method |
|---------|----------|--------|
| Site quota status | `/sites/{id}/quota/status` | GET |
| Pre-backup check | `/sites/{id}/quota/check` | GET |
| Update quota | `/sites/{id}/quota` | PUT |
| Node quota | `/nodes/{id}/quota/status` | GET |
| Storage health | `/storage/health` | GET |
| Scheduled deletions | `/backups/scheduled-deletions` | GET |
| Cancel deletion | `/backups/{id}/cancel-deletion` | DELETE |
