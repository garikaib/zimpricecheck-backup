# Managing Sites

All WordPress sites are configured in `config.json`.

## Configuration Format

Sites are defined in the `sites` array.

```json
{
  "sites": [
    {
      "name": "example-site",
      "wp_config_path": "/var/www/example.com/wp-config.php",
      "wp_content_path": "/var/www/example.com/htdocs/wp-content",
      "db_host": "localhost",
      "db_name": "example_db",
      "db_user": "db_user",
      "db_password": "secret_password"
    }
  ]
}
```

### Auto-Detection

The system can automatically detect sites in `/var/www/` and populate `config.json`.

```bash
# Run wizard to detect
./configure.sh --detect
```

### Manual Configuration

You can also edit `config.json` manually or use the wizard:

```bash
./configure.sh --sites
```

### Database Credentials

If `db_name`, `db_user`, and `db_password` are left empty (or set to `""`), the system will verify it can extract them from `wp-config.php` automatically. This is the recommended and most secure method.

Only fill these fields if:
- Your `wp-config.php` uses complex logic/variables for DB credentials that regex cannot parse.
- You are using an external database not defined in `wp-config.php`.
