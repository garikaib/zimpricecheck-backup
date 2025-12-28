# Deployment Guide

The `deploy.sh` script supports two distinct deployment targets: **Master** and **Node**.

## Prerequisites

*   **Local Machine**: Linux/Mac with `ssh`, `scp`, `python3`.
*   **Remote Server**: Ubuntu 20.04/22.04 LTS (recommended).
*   **SSH Access**: You must have SSH access to the target server (e.g., `ssh user@ip`).

## 1. Deploying the Master Server

The Master Server hosts the API, Database (SQLite), and Scheduler.

1.  **Prepare Deployment**:
    Ensure your local `.env` file or environment variables are set if needed, though `deploy.sh` prompts for target IP.

2.  **Run Deployment**:
    ```bash
    ./deploy.sh master
    ```
    *   **Prompts**: You will be asked for the Target IP and SSH User.
    *   **Actions**:
        *   Uploads Master code (`master/`) and Daemon (`daemon/`).
        *   Installs dependencies (`master/requirements.txt`).
        *   **Initializes Database**:
            *   Runs `init_db.py` which performs a **Schema Integrity Check**.
            *   Automatically adds any missing tables/columns to match code.
            *   Creates default Superuser (`garikaib@gmail.com`) with a **random password** (printed in output) if not exists.
            *   Creates Master Node record.
            *   Seeds default email channels (Pulse/SMTP).
        *   Sets up `systemd` service: `wordpress-master.service`.

3.  **Verify**:
    ```bash
    curl https://<master-domain>/api/v1/storage/health
    # {"healthy": true, ...}
    ```

## 2. Deploying a Backup Node

Nodes are the servers running WordPress that perform the actual backups.

1.  **Run Deployment**:
    ```bash
    ./deploy.sh node
    ```
    *   **Prompts**: You will be asked for the Target IP, SSH User, Master URL, and API Key.
    *   **Actions**:
        *   Uploads Daemon code (`daemon/`).
        *   **Optimized Code**: Automatically refactors `main.py` to remove Master dependencies.
        *   Installs dependencies (`daemon/requirements.txt`).
        *   Configures `systemd` service: `wordpress-backup.service`.
        *   Registers the node with the Master.

2.  **Activation**:
    *   The node enters a **PENDING** state upon registration.
    *   Admin must log in to the Master Dashboard (or use API) to **Approve** the node.
    *   Once approved, the node will begin polling for jobs.

3.  **Verify**:
    Check the service status on the node:
    ```bash
    ssh user@node-ip "systemctl status wordpress-backup"
    ```

## 3. Database Management

The Master Server uses a robust self-healing database strategy.

*   **Integrity Check**: On every deployment (`init_db.py`), the system checks the live SQLite database against the SQLAlchemy models.
*   **Auto-Migration**: Missing tables and columns are automatically detected and added. giving you a "permanent fix" for schema drift.
*   **Permissions**: `deploy.sh` enforces correct file ownership `chown user:user` on the database file to prevent `readonly database` errors.

## Troubleshooting

*   **"OperationalError: no such column"**: This means the DB is out of sync. Re-run deployment or execute `python3 master/init_db.py` on the server to trigger the integrity check.
*   **"readonly database"**: Use `deploy.sh` to redeploy, which reapplies permission fixes.
*   **Service Failures**:
    ```bash
    journalctl -u wordpress-master -f  # Master
    journalctl -u wordpress-backup -f  # Node
    ```
