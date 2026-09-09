# Base de datos — CRM Clínica Satori

## Estado actual

Se provisionó y validó un servidor **PostgreSQL 16** local con el esquema completo de `schema.sql` ya ejecutado, probado y con datos semilla cargados.

## Credenciales de desarrollo

```
Host:     localhost
Puerto:   5432
Base:     satori_crm
Usuario:  satori_app
Password: satori_dev_2026
```

Cadena de conexión (para el backend, en `.env`):
```env
DATABASE_URL=postgresql+asyncpg://satori_app:satori_dev_2026@localhost:5432/satori_crm
DATABASE_URL_SYNC=postgresql://satori_app:satori_dev_2026@localhost:5432/satori_crm
```

> Estas credenciales son de **desarrollo local únicamente**. Deben rotarse antes de cualquier despliegue a staging/producción.

## Qué se validó

- ✅ 20 tablas creadas sin errores (incluye las 5 tablas nuevas: `users` con endpoints reales, `refresh_tokens`, `webhook_events`, `notifications`, `document_counters`).
- ✅ Extensiones `pgcrypto` (UUIDs) y `pg_trgm` (búsqueda difusa) instaladas.
- ✅ Función `next_document_number()` probada: genera `COT-2026-000001`, `COT-2026-000002`, `FAC-2026-000001` de forma secuencial y atómica (sin condición de carrera, ver `INSERT ... ON CONFLICT DO UPDATE`).
- ✅ Trigger de coherencia de negocio probado: una `opportunity` en un pipeline `b2b` sin `company_id` es **rechazada** por la base de datos con el mensaje `Una oportunidad en un pipeline B2B requiere company_id`. Una oportunidad válida en `b2c` con `contact_id` se inserta correctamente.
- ✅ Seed inicial cargado: 2 pipelines (`Pipeline B2C` con 7 etapas, `Pipeline B2B` con 9 etapas) y 1 usuario `admin@clinicasatori.cr`.
- ⚠️ El `password_hash` del usuario admin sembrado es un **placeholder**. Debe regenerarse con el mecanismo real de hashing del backend (argon2id, ver especificación de backend §15) antes de usarlo — no está pensado para producción tal cual.

## Cómo replicar este entorno en otra máquina

```bash
# 1. Instalar PostgreSQL 16 (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# 2. Crear rol y base de datos
sudo -u postgres psql -c "CREATE ROLE satori_app WITH LOGIN PASSWORD 'satori_dev_2026' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE satori_crm OWNER satori_app;"

# 3. Aplicar el esquema
PGPASSWORD=satori_dev_2026 psql -h localhost -U satori_app -d satori_crm -f schema.sql
```

## Siguientes pasos (a cargo del equipo de desarrollo)

1. Conectar el backend FastAPI usando `DATABASE_URL` de arriba.
2. Inicializar Alembic apuntando a este esquema como punto de partida (`alembic stamp head` tras marcar el estado actual como la migración base), de modo que todo cambio futuro se gestione por migraciones versionadas, no editando `schema.sql` directamente.
3. Regenerar el hash del usuario admin con el endpoint real de creación de usuarios (o un script de seed que use la misma función de hashing del backend).
