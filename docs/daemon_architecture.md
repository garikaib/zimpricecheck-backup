# Backupd Architecture

The new `backupd` daemon is a modular, event-driven backup service designed to run in either **Master** or **Node** mode.

## Core Components

### 1. Modes of Operation
- **Master Mode** (`--mode master`):
  - runs the FastAPI server (`master.main:app`).
  - Manages the database, scheduling, and API.
  - Distributes jobs to nodes.
- **Node Mode** (`--mode node`):
  - Runs as a lightweight agent.
  - Registers with the Master via API.
  - Polls for jobs or receives commands (future: WebSocket).
  - Executes backup modules.
- **Auto-Detection**: The daemon detects its mode via `BACKUPD_MODE` env var or config file.

### 2. Resource Manager
To prevent system overload, `backupd` uses a centrally managed `ResourceManager` (`daemon/resource_manager.py`) with semaphores and thread pools:
- **Max Concurrent I/O**: Defaults to 2 heavy I/O tasks.
- **Max Concurrent Network**: Defaults to 2 concurrent uploads.
- **Bandwidth Limiting**: Global upload speed limit (default: unlimited, configurable).
- **CPU Pooling**: ThreadPoolExecutor for CPU-intensive tasks (e.g., compression).

### 3. Job Queue
Jobs are managed via a priority queue (`daemon/job_queue.py`).
- **Priorities**: High (10) to Low (0).
- **States**: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.
- **Stages**: Each job is broken down into granular stages (e.g., `backup_db`, `upload`).
- **Resume Capability**: (Future) Jobs track their current stage for potential resumption.

### 4. Modular System
Backup logic is encapsulated in **Modules** (`daemon/modules/`).
- **Base Class**: `BackupModule` (ABC) defines the interface.
- **Registry**: Modules self-register at runtime.
- **Configuration**: Each module defines its own config schema.

#### WordPress Module (`daemon/modules/wordpress.py`)
Stages:
1. **backup_db**: Dumps database using `mysqldump`.
2. **backup_files**: Copies `wp-content` (plugins, themes, uploads).
3. **create_bundle**: Compresses data using `tar` + `zstd`.
4. **upload_remote**: Uploads bundle to configured Storage Provider (S3, B2, etc.) via Master credentials.
5. **cleanup**: Cleans up temporary files.

## Configuration

### Environment Variables
- `BACKUPD_MODE`: `master` or `node`
- `BACKUPD_MASTER_URL`: URL of Master API (Node mode)
- `BACKUPD_API_KEY`: API Key for Master (Node mode)
- `BACKUPD_DATA_DIR`: Base directory for local data
- `BACKUPD_MAX_IO`: Max concurrent I/O ops
- `BACKUPD_MAX_NETWORK`: Max concurrent network ops
- `BACKUPD_MAX_BANDWIDTH_MBPS`: Upload speed limit

### Node Registration
1. **Startup**: Node generates a random 5-character code (e.g., `XC9D2`).
2. **Display**: Code is logged/displayed on the node console.
3. **Approval**: Admin enters this code in the Master Dashboard.
4. **Activation**: Master verifies code, sets IP, and activates the node.
5. **Auth**: Node receives a permanent API Key for future requests.

## Storage Security
- **Providers**: Configured centrally on the Master.
- **Encryption**: Credentials (Access/Secret keys) are encrypted at rest using Fernet (symmetric).
- **Distribution**: Nodes fetch decrypted credentials *only* for the assigned provider when needed.
