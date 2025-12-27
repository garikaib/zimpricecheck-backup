# Managing Sites

Sites are the core entities of the backup system.

## Detection Workflow

1.  **Auto-Detection**: The Daemon scans `/var/www` (or other configured paths) for `wp-config.php` files.
2.  **Registration**: Found sites are sent to the Master API (`POST /sites/scan`).
3.  **Approval/Visibility**: Sites appear in the Dashboard.
4.  **Activation**: Sites are by default active once detected, unless explicitly excluded.

## Manual Configuration (Optional)

In rare cases where auto-detection fails (e.g., non-standard paths), you can enforce site inclusion via `config.json` on the Node.

```json
{
  "sites": [
    {
      "name": "custom-wp",
      "wp_path": "/opt/custom-apps/wordpress"
    }
  ]
}
```

## Database Credentials

The system parses `wp-config.php` to find database credentials. It supports:
- Standard `DB_NAME`, `DB_USER`, `DB_PASSWORD` definitions.
- Variable interpolation (basic).

If your config is highly dynamic (e.g., fetches secrets from environment variables at runtime), you may need to supply credentials manually in `config.json` or ensure the daemon runs with those environment variables set.

## Exclusions

To prevent a detected site from being backed up:
1.  **Preferred**: Disable it in the Master Dashboard.
2.  **Local**: Add `"skip": true` to `config.json` for that site.
