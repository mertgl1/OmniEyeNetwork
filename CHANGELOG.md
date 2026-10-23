# Changelog

All notable changes to **OmniEyeNetwork** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] - 2026-10-23

### Added
- **Phase 4 network inventory synchronization**:
  - Hourly Celery Beat port/VLAN/MAC discovery and per-device worker tasks.
  - Read-only vendor command output parsing and database upsert for discovered ports.
  - `POST /api/v1/ports/discovery/run` for authorized discovery dispatch.
  - `GET /api/v1/devices/{id}/live-config` for on-demand live configuration.
- **Phase 5 Vue management console**:
  - Vue 3 + TypeScript + Vite + Tailwind 4 single-page application.
  - Login, role-aware device/group dashboard, port status view, device enrollment, and live configuration display.
  - xterm.js WebSocket console restricted to vendor-profile read-only interface/VLAN/MAC/version commands.
- **Docker services and operations**:
  - Frontend/Nginx container with API and WebSocket proxying.
  - Celery Beat service with nightly backup and hourly discovery schedules.
  - Alembic baseline migration for empty and existing SQLAlchemy-created databases.

### Security
- Protected inventory and backup routes with current-user and role checks; restricted backup payload and diff access to admins/operators.
- Rechecked the current DB role against each JWT and invalidated tokens after role changes.
- Replaced new local password hashes with PBKDF2-HMAC-SHA256 and upgrade legacy hashes on login.
- Escaped LDAP search filters, enabled LDAPS certificate validation, and made mock AD opt-in outside the development template.
- Removed fabricated-success fallback after a failed SSH connection; simulation is now explicit.
- Added production startup validation, frontend security headers, loopback-only service bindings, and a critical warning for legacy development Vault-key derivation.

### Changed
- Bulk backups now dispatch per-device Celery tasks instead of performing network I/O inside the API request.
- Updated README and architecture documentation to match implemented APIs, role boundaries, schedules, frontend, and deployment requirements.
- Corrected group deletion behavior so devices are detached rather than deleted.

## [0.3.0] - 2026-10-23

### Added
- **Multi-Vendor Command Matrix (`vendor_profiles.py`)**:
  - Full CLI command mapping for major enterprise network hardware:
    - **Cisco:** IOS, IOS-XE, NX-OS (Nexus), IOS-XR
    - **Huawei:** VRP (CloudEngine, S5700, S6700, AR Routers)
    - **Aruba:** ArubaOS-CX (CX 6000, 6100, 6200, 6300, 8320)
    - **HPE:** ProCurve (2530, 2920, 2930F, 5400) and Comware / H3C (5900, 5940, 12500)
    - **Juniper:** JunOS (EX2300, EX3400, EX4300, QFX5100, SRX)
    - **Dell:** OS10 (PowerSwitch S-Series) and Force10
    - **Extreme:** EXOS (Summit Series)
    - **MikroTik:** RouterOS and Cloud Router Switches (CRS)
    - **Fortinet:** FortiSwitch and FortiOS
  - Dynamic discovery helper `get_vendor_profile()` with automatic OS type resolution.
- **Configuration Versioning & Unix Unified Diff Engine (`diff_service.py`)**:
  - SHA-256 configuration checksum computation to eliminate duplicate database storage when configurations are unchanged.
  - Line-by-line unified diff calculation (`difflib`) returning structured additions (`+`), deletions (`-`), and modification statistics.
- **Celery Asynchronous Backup Tasks (`backup_tasks.py`)**:
  - `backup_single_device_task`: Asynchronously executes SSH configuration pull for an individual device.
  - `backup_all_devices_task`: Parallel batch execution across entire inventory or specific device groups.
  - Celery Beat scheduled task ready for recurring nightly configuration backups.
- **Backup & Multi-Vendor REST API Endpoints**:
  - `POST /api/v1/backups/devices/{device_id}/run`: On-demand manual backup trigger.
  - `POST /api/v1/backups/run-all`: Bulk backup queue dispatch.
  - `GET /api/v1/backups/devices/{device_id}`: Chronological backup version history.
  - `GET /api/v1/backups/{backup_id}`: Raw configuration text retrieval.
  - `GET /api/v1/backups/diff`: Line-by-line visual difference between two configuration versions.
  - `GET /api/v1/vendors`: Catalog of all supported vendors, models, and command definitions.
- **Automated Test Suite Expansion**:
  - Vendor command set validation tests (`test_vendor_profiles.py`).
  - Hash computation, diff generation, and backup endpoint integration tests (`test_backup_and_diff.py`).

---

## [0.2.0] - 2026-10-23

### Added
- **Vault Cryptography Engine (`AES-256 Fernet`)**:
  - Secure encryption of device credentials (SSH passwords, enable secrets) using 256-bit AES with PBKDF2HMAC key derivation.
  - Automatic zero-leakage guarantee: Plaintext passwords are never returned in REST API responses (`DeviceResponse`).
- **Active Directory / LDAP & RBAC Security Layer**:
  - LDAP authentication module (`ldap.py`) supporting corporate AD domain controllers.
  - Automatic AD security group to RBAC role translation:
    - `Network_Admins` $\rightarrow$ `admin` (Full access, Vault, Web SSH, configuration changes).
    - `Network_Operators` $\rightarrow$ `operator` (Web SSH, live config display, port management).
    - `Network_Viewers` $\rightarrow$ `viewer` (Read-only access to inventory and backup history).
  - Built-in Mock authentication mode for local development and zero-dependency unit tests.
- **JWT Authentication Endpoints**:
  - `POST /api/v1/auth/login`: Issue secure HS256 JWT tokens.
  - `GET /api/v1/auth/me`: Profile and active role of authenticated user.
  - `GET /api/v1/auth/roles`: System role permissions catalog.
- **Automated Test Suite (Pytest)**:
  - 15 unit and integration tests with in-memory asynchronous SQLite (`aiosqlite`).

---

## [0.1.0] - 2026-10-23

### Added
- **Base Container Infrastructure**:
  - Multi-container `docker-compose.yml` for FastAPI, MariaDB 11.4, Redis 7.2, and Celery worker.
  - Docker healthchecks and persistent storage volumes.
  - MariaDB initialization script with `utf8mb4_unicode_ci` charset.
- **Asynchronous Database ORM Modeler (SQLAlchemy 2.0 Async)**:
  - Models for `Device`, `DeviceGroup`, `Port`, and `ConfigBackup`.
  - Alembic asynchronous database migration framework.
- **RESTful CRUD API**:
  - `/api/v1/health`: Real-time MariaDB and Redis health check.
  - `/api/v1/groups`: Device group inventory management.
  - `/api/v1/devices`: Network switch and router inventory management with vendor filtering.
  - `/api/v1/ports`: Switch port, interface status, and VLAN inventory management.
- **Documentation**:
  - Initial `README.md` and system architecture specifications in `docs/ARCHITECTURE.md`.
