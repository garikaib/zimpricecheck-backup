# Deployment Guide

The `deploy.sh` script now supports two distinct deployment targets.

## Prerequisites

*   **Local Machine**: Linux/Mac with `ssh`, `scp`, `zstd`, `python3`.
*   **Remote Server**: Ubuntu 20.04/22.04 LTS recommended.

## 1. Deploying the Master Server

The Master Server hosts the API and Database.

1.  **Configure Target**:
    ```bash
    ./configure.sh
    # Set "Remote Host" to your Master VPS IP.
    # Skip "Sites" detection (not needed for Master).
    ```

2.  **Deploy**:
    ```bash
    ./deploy.sh master
    ```
    *   Uploads standard Master code (`master/` dir).
    *   Installs dependencies (`master/requirements.txt`).
    *   Initializes DB (`init_db.py`).
    *   Installs `wordpress-master.service` (Port 8000).

3.  **Verify**:
    ```bash
    curl http://<master-ip>:8000/health
    # {"status": "ok"}
    ```

## 2. Deploying a Node Agent

Nodes are the servers running WordPress that need backup.

1.  **Configure Target & Mode**:
    ```bash
    ./configure.sh
    # 1. Set "Remote Host" to Client VPS IP.
    # 2. Select Mode: "2. Managed Node".
    # 3. Enter Master URL (http://<master-ip>:8000).
    # 4. Wait for Approval (or approve manually via API).
    # 5. Enable Site Detection (or add manually).
    ```

2.  **Deploy**:
    ```bash
    ./deploy.sh node
    ```
    *   Uploads Agent code (`lib/`, `run.sh`).
    *   installs dependencies (`requirements.txt`).
    *   Installs `wordpress-backup.service` timers.

## Troubleshooting Deployment

*   **"Yanked Version" Warning**: If you see pip warnings, check `requirements.txt`. We pin `email-validator` to avoid unstable versions.
*   **Permission Denied**: Ensure the SSH user has `sudo` rights without password prompting (or stick to `root` if necessary).
*   **Service Failures**: Check logs:
    ```bash
    journalctl -u wordpress-master -f  # Master
    journalctl -u wordpress-backup -f  # Node
    ```
