# CRM Clínica Satori — Especificación Final de Backend (Lista para Desarrollo)

**Versión:** 2.0 (consolida spec original v1.0 + revisión arquitectónica)
**Backend:** Python 3.12 + FastAPI
**Base de datos:** PostgreSQL 16 (esquema ya provisionado, ver §3)
**ORM:** SQLAlchemy 2.x (async) + Alembic
**Cola/Cache:** Redis (obligatorio desde el MVP, no opcional)
**Autenticación:** JWT de vida corta + refresh token en cookie httpOnly

Este documento reemplaza a `CRM_Clínica_Satori_-_Backend_-_REST_API.md` v1.0. Toda decisión marcada `[RESUELTO]` responde directamente a un hallazgo de `SATORI_CRM_Revision_Backend.md`.

---

## 1. Objetivo

CRM comercial para Clínica Satori (psicología B2C y B2B). Gestiona el ciclo:

```
Lead → Calificación → Contact/Company → Opportunity → Quote → Invoice → Service
```

Principio de diseño (se mantiene de la spec original, sección 41): **es un CRM comercial, no un expediente clínico.** Cualquier dato clínico sensible queda fuera de este sistema o en un módulo separado con controles de acceso propios.

---

## 2. Arquitectura

```
                    ┌──────────────────────┐
                    │   React + Tailwind   │
                    │      Frontend        │
                    └──────────┬───────────┘
                               │ HTTPS / JSON + WebSocket
                               ▼
                    ┌──────────────────────┐
                    │      FastAPI         │
                    │       REST API       │
                    └──────────┬───────────┘
                               │
        ┌───────────┬──────────┼──────────┬────────────────┐
        ▼           ▼          ▼          ▼                ▼
  ┌──────────┐ ┌─────────┐┌─────────┐┌───────────┐  ┌──────────────┐
  │PostgreSQL│ │  Redis  ││ Worker  ││Email/Form │  │  WhatsApp    │
  │          │ │(cola+   ││(Celery/ ││Integration│  │ Integration  │
  │          │ │ cache)  ││  arq)   │└───────────┘  └──────────────┘
  └──────────┘ └─────────┘└─────────┘
```

**[RESUELTO 2.6]** El worker asíncrono deja de ser opcional: procesa webhooks, envío de email/WhatsApp, generación de PDF pesada y notificaciones. El API nunca bloquea el request-response esperando a un proveedor externo.

---

## 3. Base de datos — Provisionada

Se generó y validó el esquema completo en un servidor PostgreSQL local. Datos de conexión para desarrollo:

```env
DATABASE_URL=postgresql+asyncpg://satori_app:satori_dev_2026@localhost:5432/satori_crm
DATABASE_URL_SYNC=postgresql://satori_app:satori_dev_2026@localhost:5432/satori_crm   # para Alembic
```

> ⚠️ Estas credenciales son **solo para el entorno de desarrollo local**. En staging/producción deben rotarse y gestionarse vía secret manager (Heroku Config Vars, Doppler, etc.), nunca en el repositorio.

El archivo `schema.sql` (entregado junto a este documento) contiene el DDL completo ya ejecutado, con:

- 20 tablas, incluyendo las 5 tablas nuevas exigidas por la revisión: `refresh_tokens`, `webhook_events`, `notifications`, `document_counters`, y `users` con endpoints (antes solo existía como tabla huérfana).
- **Tipos ENUM nativos** en vez de `VARCHAR` libres para todo campo de estado/tipo (`[RESUELTO 3.1]`), lo que elimina typos silenciosos a nivel de base de datos.
- **Soft delete** (`deleted_at TIMESTAMPTZ`) en `users`, `leads`, `contacts`, `companies`, `services`, `opportunities`, `quotes`, `invoices`, `activities` (`[RESUELTO 2.1]`). Índices únicos son parciales (`WHERE deleted_at IS NULL`) para permitir reutilizar un email/código tras una baja.
- **Función `next_document_number()`** para numeración atómica de cotizaciones y facturas vía `INSERT ... ON CONFLICT DO UPDATE`, sin condición de carrera (`[RESUELTO 2.3]`). Formato: `COT-2026-000001` / `FAC-2026-000001`.
- **Triggers de integridad de negocio**: una `opportunity` en un pipeline `b2b` exige `company_id`; una en `b2c` exige `contact_id`; la etapa (`stage_id`) debe pertenecer al `pipeline_id` indicado (`[RESUELTO 4.2]`).
- **Índices `pg_trgm`** en `leads`, `contacts`, `companies` para soportar búsqueda difusa/global desde el día uno (`[RESUELTO 3.5]`).
- Seed inicial: 2 pipelines (B2C con 7 etapas, B2B con 9 etapas) según lo definido en la spec original, y un usuario `admin` de arranque (su `password_hash` debe regenerarse con el mecanismo de hashing real del backend — el valor en el seed es un placeholder).

**Aplicar el esquema en otro entorno:**
```bash
createdb -U <owner> satori_crm
psql -U <owner> -d satori_crm -f schema.sql
```

A partir de aquí, todo cambio de esquema se maneja con **Alembic** (migraciones versionadas); `schema.sql` es el punto de partida congelado, no se vuelve a ejecutar manualmente en ambientes ya inicializados.

---

## 4. Estructura del proyecto

```
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py          # hashing (argon2/bcrypt), JWT, cookies
│   │   ├── database.py
│   │   ├── permissions.py       # [NUEVO] matriz rol → capacidades (§6)
│   │   └── queue.py             # [NUEVO] cliente Celery/arq + Redis
│   ├── models/            # incluye User, Lead, Contact, Company, Service,
│   │                       # Pipeline, PipelineStage, Opportunity, Quote,
│   │                       # Invoice, Activity, Communication,
│   │                       # RefreshToken, WebhookEvent, Notification, AuditLog
│   ├── schemas/
│   ├── api/v1/
│   │   ├── auth.py
│   │   ├── users.py              # [NUEVO]
│   │   ├── leads.py
│   │   ├── contacts.py
│   │   ├── companies.py
│   │   ├── services.py
│   │   ├── pipelines.py
│   │   ├── opportunities.py
│   │   ├── quotes.py
│   │   ├── invoices.py
│   │   ├── activities.py
│   │   ├── communications.py
│   │   ├── notifications.py      # [NUEVO]
│   │   ├── search.py             # [NUEVO]
│   │   ├── webhooks.py
│   │   └── health.py             # [NUEVO]
│   ├── services/
│   │   ├── lead_service.py       # incluye deduplicación y conversión transaccional
│   │   ├── quote_service.py      # incluye conversión a factura
│   │   ├── invoice_service.py
│   │   ├── pdf_service.py        # [NUEVO] WeasyPrint
│   │   ├── notification_service.py  # [NUEVO]
│   │   ├── email_service.py
│   │   └── whatsapp_service.py   # incluye lógica de ventana de 24h
│   ├── workers/                  # [NUEVO] tareas Celery/arq
│   │   ├── webhook_tasks.py
│   │   ├── notification_tasks.py
│   │   └── pdf_tasks.py
│   ├── realtime/                 # [NUEVO] WebSocket/SSE manager
│   │   └── ws_manager.py
│   └── repositories/
├── migrations/          # Alembic
├── tests/
├── requirements.txt
├── alembic.ini
└── .env
```

---

## 5. Autenticación y sesiones `[RESUELTO frontend 2.1 / backend 4.4-4.5]`

- **Access token JWT**: vida de 15 minutos. El frontend lo mantiene solo en memoria (nunca `localStorage`).
- **Refresh token**: opaco (no JWT), se guarda **hasheado** (`token_hash`) en la tabla `refresh_tokens` y se entrega al navegador como cookie `httpOnly + Secure + SameSite=Strict`. Permite revocación individual (ej. al desactivar un usuario, se marcan `revoked_at` todas sus filas).

Endpoints:
```http
POST /auth/login              → set-cookie refresh_token; body: { access_token, user }
POST /auth/refresh             → lee cookie, valida hash, rota el refresh token, devuelve nuevo access_token
POST /auth/logout              → revoca el refresh token actual
GET  /auth/me                  → { user, role, capabilities: [...] }
POST /auth/forgot-password     → [NUEVO] genera token de un solo uso, vida 30 min
POST /auth/reset-password      → [NUEVO]
```

`GET /auth/me` devuelve **capacidades explícitas**, no solo el rol crudo, para que el frontend nunca tenga que mantener su propia copia de la matriz rol→permiso (`[RESUELTO frontend 4.6]`):

```json
{
  "user": { "id": "...", "first_name": "...", "role": "sales" },
  "capabilities": [
    "leads:read", "leads:write", "leads:convert",
    "contacts:read", "contacts:write",
    "companies:read", "companies:write",
    "opportunities:read", "opportunities:write",
    "quotes:read", "quotes:write", "quotes:send",
    "pipeline:move"
  ]
}
```

---

## 6. RBAC — Matriz de permisos por rol `[RESUELTO 3.2]`

| Recurso | admin | manager | sales | therapist | accounting |
|---|---|---|---|---|---|
| Leads (CRUD + convertir) | ✅ | ✅ | ✅ | ❌ | ❌ |
| Contactos / Empresas | ✅ | ✅ | ✅ | ver + editar propios | ❌ |
| Pipeline / Oportunidades | ✅ | ✅ | ✅ | ❌ | ❌ |
| Cotizaciones | ✅ | ✅ | ✅ (crear/enviar) | ❌ | ver |
| Facturas | ✅ | ✅ | ver | ❌ | ✅ (crear/marcar pagada) |
| Actividades | ✅ | ✅ | ✅ | ✅ (solo propias/asignadas) | ❌ |
| Comunicaciones (Email/WhatsApp) | ✅ | ✅ | ✅ | ver | ❌ |
| Servicios (catálogo) | ✅ | ✅ | ver | ver | ver |
| Usuarios / Configuración | ✅ | ❌ | ❌ | ❌ | ❌ |
| Reportes / Dashboard | ✅ | ✅ | vista limitada (propia cartera) | ❌ | financiero |
| Auditoría | ✅ | ver | ❌ | ❌ | ❌ |

Implementar como dependencia de FastAPI (`Depends(require_capability("quotes:send"))`) que valida contra la lista de capacidades del rol, definida centralmente en `core/permissions.py`. Cambiar el permiso de un rol es editar un solo archivo, no buscar `if role ==` disperso en cada endpoint.

---

## 7. REST API completa

Base: `/api/v1`

### Auth (§5)
Ya detallado arriba.

### Users `[NUEVO — RESUELTO 2.2]`
```http
GET    /users                      (admin)
POST   /users                      (admin)
GET    /users/{id}                 (admin)
PUT    /users/{id}                 (admin)
POST   /users/{id}/deactivate      (admin) — soft delete + revoca refresh_tokens
POST   /users/{id}/reset-password  (admin)
```

### Leads
```http
GET    /leads?status&source&lead_type&assigned_to&created_from&created_to&search&page&page_size
POST   /leads
GET    /leads/{id}
PUT    /leads/{id}
DELETE /leads/{id}                 → soft delete
POST   /leads/{id}/convert
POST   /leads/{id}/assign
```

### Contacts / Companies / Services
```http
GET/POST/PUT/DELETE  /contacts[..]
GET/POST/PUT/DELETE  /companies[..]
GET/POST/PUT/DELETE  /services[..]
```
Todos con `?page&page_size&search` y respuesta paginada estándar (§8).

### Pipelines / Opportunities
```http
GET/POST   /pipelines
GET/PUT    /pipelines/{id}
GET/POST   /pipelines/{id}/stages

GET/POST   /opportunities
GET/PUT/DELETE /opportunities/{id}
POST /opportunities/{id}/move
POST /opportunities/{id}/won
POST /opportunities/{id}/lost
```

### Quotes
```http
GET/POST      /quotes
GET/PUT/DELETE /quotes/{id}
POST /quotes/{id}/send
POST /quotes/{id}/accept
POST /quotes/{id}/reject
POST /quotes/{id}/convert-to-invoice   [NUEVO — RESUELTO 3.4]  (solo si status=accepted)
GET  /quotes/{id}/pdf                  [NUEVO — RESUELTO 3.3]
```

### Invoices
```http
GET/POST   /invoices
GET/PUT    /invoices/{id}
POST /invoices/{id}/send
POST /invoices/{id}/mark-paid
POST /invoices/{id}/cancel
GET  /invoices/{id}/pdf                [NUEVO]
```

### Activities / Communications
```http
GET/POST/PUT/DELETE  /activities[..]
POST /activities/{id}/complete

GET  /communications
GET  /communications/{id}
```

### Notifications `[NUEVO — RESUELTO 3.6]`
```http
GET  /notifications?unread_only=true
POST /notifications/{id}/read
POST /notifications/read-all
```

### Search `[NUEVO — RESUELTO 3.5]`
```http
GET /search?q=texto
→ [{ entity_type: "lead", id, label, subtitle }, { entity_type: "quote", ... }, ...]
```
Implementado con `pg_trgm` (índices ya creados en `schema.sql`) sobre `leads`, `contacts`, `companies`, `quotes.quote_number`, `invoices.invoice_number`.

### Timeline `[NUEVO — RESUELTO frontend 4.3]`
```http
GET /timeline?entity_type=lead&entity_id={id}
```
Devuelve ya mezclado y ordenado por fecha: activities + communications + cambios de estado + eventos de quotes/invoices relacionados. Evita que el frontend haga 4 fetches y los mezcle client-side.

### Dashboard
```http
GET /dashboard
```
(Igual a spec original, sección 12.)

### Webhooks
```http
POST /webhooks/email
POST /webhooks/whatsapp
```

### Health `[NUEVO]`
```http
GET /health           → liveness
GET /health/ready      → valida conexión a DB y Redis
```

---

## 8. Convención de paginación `[RESUELTO 3.8]`

Todo `GET` de listado usa `page` (default 1) y `page_size` (default 25, máx 100), y responde:

```json
{
  "items": [ ... ],
  "total": 245,
  "page": 1,
  "page_size": 25,
  "total_pages": 10
}
```

---

## 9. Webhooks: idempotencia y desacople `[RESUELTO 2.5]`

Flujo:

```
1. Request entra a POST /webhooks/{provider}
2. Validar firma (X-Hub-Signature-256 para Meta, equivalente para el proveedor de email)
3. INSERT en webhook_events (provider, external_event_id, payload)
   → si external_event_id ya existe (índice único), responder 200 inmediatamente sin reprocesar
4. Encolar tarea en el worker (webhook_tasks.process_event(webhook_event_id))
5. Responder 200 al proveedor en <1s
   (el procesamiento real — crear/actualizar Lead, guardar Communication,
    generar Activity — ocurre de forma asíncrona en el worker)
```

Esto resuelve tanto la deduplicación (reintentos del proveedor no crean leads duplicados) como el riesgo de timeout (Meta puede desactivar un webhook que responde lento).

---

## 10. Deduplicación `[RESUELTO 3.7]`

Extendida más allá de Leads (spec original §8):

- **Leads**: buscar por email → teléfono normalizado → whatsapp normalizado. Si existe, actualizar; si no, crear.
- **Contacts / Companies**: al crear directamente (fuera del flujo de conversión), buscar coincidencia por email (contacts) o `tax_id` (companies). Si hay coincidencia, **advertir** en la respuesta (`possible_duplicate: {id, name}`) sin bloquear la creación — un bloqueo duro genera fricción cuando la coincidencia es casual.
- Normalización de teléfono: función utilitaria que remueve espacios/guiones y homologa el prefijo `+506` para números costarricenses antes de comparar.

---

## 11. Conversión de Lead `[RESUELTO 2.4]`

`POST /leads/{lead_id}/convert` ejecuta **una sola transacción de base de datos**:

```python
async with session.begin():
    contact = create_contact(...)
    if lead.lead_type == "company":
        company = create_or_match_company(...)
        contact.company_id = company.id
    opportunity = create_opportunity(pipeline=..., contact=contact, company=company)
    lead.status = "converted"
    lead.converted_at = now()
```

Si cualquier paso falla, todo se revierte — nunca queda un `Contact` huérfano sin `Opportunity`. **Idempotencia:** si el lead ya tiene `status = converted`, el endpoint responde `409 Conflict` con la referencia a la oportunidad ya creada, en vez de generar una segunda conversión.

---

## 12. Generación de PDF `[RESUELTO frontend 3.3]`

- Se genera **en el backend** con WeasyPrint (consistente con otros proyectos del mismo stack).
- `GET /quotes/{id}/pdf` y `GET /invoices/{id}/pdf` generan on-demand para MVP.
- Al **enviar** una cotización/factura (`POST /quotes/{id}/send`), se genera y almacena una copia inmutable (`pdf_path` en la tabla, ya incluido en `schema.sql`) — así el PDF que el cliente recibió no cambia si luego alguien edita la cotización en el sistema.

---

## 13. Notificaciones y tiempo real `[RESUELTO 3.6 / frontend 2.3]`

- Tabla `notifications` ya provisionada.
- Se generan desde `services/notification_service.py` en los eventos de negocio relevantes: nueva asignación de lead, nueva actividad, cotización aceptada, factura vencida.
- **Push en vivo**: WebSocket (`/ws/notifications`) autenticado con el mismo JWT. Al crear una `Communication` entrante o una `Notification`, el backend emite el evento a los sockets conectados del usuario correspondiente. El frontend usa esto solo para invalidar caché de TanStack Query, no para reemplazar el modelo de datos REST.

---

## 14. Integración WhatsApp — ventana de 24 horas `[RESUELTO 3.9]`

`communications.is_template` (ya en el esquema) distingue mensajes de formato libre de mensajes de plantilla pre-aprobada. `whatsapp_service.py` debe calcular, antes de enviar, si han pasado más de 24h desde el último mensaje **entrante** del contacto:

- Si la ventana está abierta → mensaje de texto libre.
- Si está cerrada → forzar el uso de una plantilla aprobada (rechazar el envío de texto libre con `422` y mensaje explicativo, no fallar silenciosamente contra la API de Meta).

---

## 15. Seguridad

- Hashing de contraseñas: **argon2id** (preferido sobre bcrypt en proyectos nuevos).
- Rate limiting: `slowapi` + Redis, por IP y por usuario autenticado.
- CORS: orígenes explícitos por ambiente (`CORS_ORIGINS`).
- Validación de firma de webhooks obligatoria antes de cualquier procesamiento.
- Principio de mínimo privilegio aplicado vía la matriz de §6.
- Cumplimiento **Ley N.º 8968** (Costa Rica, protección de datos personales): formularios web deben incluir aviso de tratamiento de datos; se debe poder atender solicitudes de acceso/rectificación/eliminación (el soft-delete + `audit_logs` ya dan la trazabilidad necesaria).

---

## 16. Variables de entorno (`.env`)

```env
APP_NAME=Clinica Satori CRM
APP_ENV=development

DATABASE_URL=postgresql+asyncpg://satori_app:satori_dev_2026@localhost:5432/satori_crm

REDIS_URL=redis://localhost:6379/0

SECRET_KEY=<generar con: openssl rand -hex 32>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=http://localhost:5173

EMAIL_PROVIDER=...
EMAIL_API_KEY=...

WHATSAPP_PROVIDER=...
WHATSAPP_API_KEY=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_APP_SECRET=...   # para validar firma de webhook
```

---

## 17. Docker (desarrollo)

```yaml
services:
  api:
    build: .
    env_file: .env
    depends_on: [postgres, redis]
    ports: ["8000:8000"]

  worker:
    build: .
    command: celery -A app.workers worker --loglevel=info
    env_file: .env
    depends_on: [postgres, redis]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: satori_app
      POSTGRES_PASSWORD: satori_dev_2026
      POSTGRES_DB: satori_crm
    volumes: ["pgdata:/var/lib/postgresql/data"]
    ports: ["5432:5432"]

  redis:
    image: redis:7
    ports: ["6379:6379"]

volumes:
  pgdata:
```

---

## 18. Plan de desarrollo (fases)

**Fase 0 — Fundaciones (antes de cualquier feature):**
Esquema de base de datos (✅ ya provisionado), autenticación completa (login/refresh/logout/me), matriz de permisos, paginación estándar, health checks.

**Fase 1 — MVP núcleo:**
Users, Leads (+ deduplicación + conversión transaccional), Contacts, Companies, Services, Pipeline, Opportunities (+ move/won/lost).

**Fase 2:**
Quotes (+ numeración + PDF + envío), Invoices (+ conversión desde Quote), Activities.

**Fase 3:**
Webhooks (email/WhatsApp) con cola asíncrona, Communications, Notifications + WebSocket, Search global, Dashboard con métricas reales, Audit log completo.

---

## 19. Definition of Done (por endpoint)

- [ ] Validación de entrada con Pydantic (schemas en `schemas/`).
- [ ] Autorización verificada contra la matriz de capacidades (§6).
- [ ] Paginación estándar aplicada si es un listado.
- [ ] Escritura en `audit_logs` si la acción es CREATE/UPDATE/DELETE/CONVERT/SEND_QUOTE/ACCEPT_QUOTE/CREATE_INVOICE/MARK_PAID.
- [ ] Prueba de integración (happy path + al menos un caso de error 4xx).
- [ ] Documentado en OpenAPI (`summary`, `description`, ejemplo de respuesta).
