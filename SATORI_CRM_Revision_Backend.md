# CRM Clínica Satori — Revisión Técnica: Backend (REST API)

**Documento:** Observaciones y recomendaciones de arquitectura
**Revisor:** Arquitectura de Sistemas Web
**Basado en:** `CRM_Clínica_Satori_-_Backend_-_REST_API.md` (v1.0)
**Fecha de revisión:** Septiembre 2026

---

## 1. Resumen ejecutivo

La especificación es sólida como punto de partida: el stack (FastAPI + PostgreSQL + SQLAlchemy 2.x + Alembic + JWT) es apropiado para el tamaño del proyecto, el modelo de entidades refleja correctamente el ciclo comercial Lead → Contact/Company → Opportunity → Quote → Invoice, y la separación en `services/` y `repositories/` es una buena práctica de capas.

Sin embargo, el documento describe un **modelo conceptual**, no una especificación lista para construir. Faltan decisiones críticas de integridad de datos, concurrencia, seguridad operativa y procesamiento asíncrono que, si no se resuelven ahora, generan deuda técnica cara de corregir después (especialmente en numeración de documentos legales, borrado de datos y procesamiento de webhooks).

Clasificación de hallazgos:

| Severidad | Cantidad |
|---|---|
| 🔴 Crítico | 6 |
| 🟠 Alto | 9 |
| 🟡 Medio | 8 |
| 🟢 Bajo / mejora | 5 |

---

## 2. Hallazgos críticos 🔴

### 2.1 Borrado físico (`DELETE`) sobre entidades con historial de negocio
Los endpoints `DELETE /leads/{id}`, `/contacts/{id}`, `/opportunities/{id}`, `/activities/{id}` realizan borrado físico. Esto es incompatible con:
- La tabla `audit_logs` (sección 14), que pierde sentido si el registro relacionado desaparece.
- Reportes históricos del dashboard (leads por fuente/estado a través del tiempo).
- Integridad referencial: `contacts.lead_id`, `opportunities.lead_id`, `quotes.contact_id`, etc. quedarían huérfanos o forzarían `ON DELETE CASCADE` no documentado, borrando cotizaciones/facturas relacionadas.

**Recomendación:** Implementar **soft delete** (`deleted_at TIMESTAMP NULL`) en todas las entidades de negocio. `DELETE` pasa a ser un `UPDATE deleted_at = now()`, y todos los `SELECT` deben filtrar `deleted_at IS NULL` por defecto (recomiendo un mixin de SQLAlchemy + un query filter global). Reservar el borrado físico para un job de purga programado (cumplimiento de retención de datos), nunca para el flujo interactivo del usuario.

### 2.2 Ausencia de endpoints de gestión de usuarios
El módulo `Administración → Usuarios` existe en el frontend (`/settings/users`) y la tabla `users` está definida, pero **no hay ningún endpoint** `GET/POST/PUT /users` en la sección 10. Solo existe `/auth/login`, `/auth/refresh`, `/auth/me`.

**Recomendación:** Agregar `GET /users`, `POST /users`, `GET/PUT /users/{id}`, `POST /users/{id}/deactivate`, y `POST /users/{id}/reset-password`. Restringir a rol `admin`.

### 2.3 Generación de numeración de documentos sin control de concurrencia
`quote_number` e `invoice_number` son `VARCHAR(50) UNIQUE`, pero no se especifica cómo se generan. Si se implementa como "buscar el máximo actual + 1" en código de aplicación, **dos requests concurrentes generarán el mismo número** (condición de carrera clásica), lo cual es inaceptable para documentos con validez fiscal/legal.

**Recomendación:** Usar una secuencia nativa de PostgreSQL (`SEQUENCE`) o un bloqueo `SELECT ... FOR UPDATE` sobre una tabla de contadores (`document_counters`) dentro de la misma transacción que crea el `quote`/`invoice`. Definir el formato desde ahora (ej. `COT-2026-000123`, `FAC-2026-000123`) incluyendo si el correlativo reinicia por año.

### 2.4 Conversión de Lead sin garantía transaccional explícita
`POST /leads/{lead_id}/convert` crea potencialmente `Contact` + `Company` + `Opportunity` en una sola operación (sección 9), pero no se indica que esto deba ejecutarse dentro de una única transacción de base de datos.

**Recomendación:** Envolver la conversión completa en una transacción (`async with session.begin():`). Si falla la creación de `Opportunity`, no debe quedar un `Contact`/`Company` huérfano. Documentar explícitamente el comportamiento de idempotencia: ¿qué pasa si se llama `/convert` dos veces sobre el mismo lead?

### 2.5 Webhooks sin idempotencia ni desacople del procesamiento
La sección 11 indica que los webhooks deben "evitar duplicados" y "procesar mensaje", pero no define **cómo**. Un proveedor de WhatsApp o email puede reintentar la entrega del mismo evento varias veces (comportamiento estándar en Meta Cloud API). Si el webhook procesa síncronamente (buscar/crear lead, guardar communication, etc.) dentro del propio request HTTP, dos problemas surgen:
- Sin una clave de idempotencia persistida, un reintento del proveedor duplica el `Lead`/`Communication`.
- Procesar todo síncronamente arriesga exceder el timeout que el proveedor tolera para el ACK del webhook (Meta espera respuesta rápida, o reintenta y puede eventualmente desactivar el webhook).

**Recomendación:**
1. Agregar tabla `webhook_events (id, provider, external_event_id UNIQUE, payload JSONB, status, received_at, processed_at)` para deduplicar por `external_event_id`.
2. El endpoint del webhook debe **responder 200 inmediatamente** tras persistir el evento crudo, y delegar el procesamiento real a una cola (ver 2.6).

### 2.6 No existe mecanismo de procesamiento asíncrono / cola de trabajos
Redis aparece en `docker-compose.yml` como "opcional", pero el documento ya exige procesamiento de webhooks, envío de emails y WhatsApp — todas operaciones que no deben bloquear el request-response del API ni fallar silenciosamente.

**Recomendación:** Definir desde el MVP un worker asíncrono (Celery, RQ o `arq`, todas compatibles con Redis) para: envío de emails/WhatsApp salientes, procesamiento de webhooks entrantes, y generación de PDF (si es pesada). Sin esto, un proveedor de email lento puede hacer que un endpoint de creación de cotización tarde varios segundos o falle en cascada.

---

## 3. Hallazgos de severidad alta 🟠

### 3.1 Tipos de dato "libres" para campos que son en realidad enumeraciones
`lead_type`, `status`, `source`, `service_type`, `billing_type`, `channel`, `direction`, etc. se definen como `VARCHAR` con una lista de valores permitidos documentada solo como texto libre. Nada impide insertar `"convertd"` por un typo.

**Recomendación:** Usar `ENUM` nativo de PostgreSQL (o al menos un `CHECK constraint`) para cada uno de estos campos. SQLAlchemy 2.x soporta `Enum` de forma directa y esto además mejora la documentación automática de OpenAPI/Swagger.

### 3.2 Falta de matriz de permisos por endpoint
Se listan 5 roles (`admin, manager, sales, therapist, accounting`), pero ningún endpoint especifica qué rol puede hacer qué. La sección 13 menciona "Role Based Access Control" como principio, no como diseño.

**Recomendación:** Antes de codificar, producir una matriz explícita rol × endpoint (ej. tabla en el propio documento). Ejemplo de riesgo concreto: ¿puede `therapist` ver `invoices`? La respuesta de negocio (sección 41: "CRM comercial") sugiere que no, pero no está definida.

### 3.3 Sin endpoint de generación de PDF
El frontend requiere "Generar PDF" tanto en Cotizaciones como en Facturas, pero la sección 10 no define `GET /quotes/{id}/pdf` ni `GET /invoices/{id}/pdf`. Dado que Greivin ya usa WeasyPrint en otros proyectos, es razonable estandarizar aquí también.

**Recomendación:** Agregar los endpoints y decidir si el PDF se genera on-demand (recomendado para MVP) o se almacena una copia inmutable en storage (recomendado en cuanto exista firma/envío legal, para que el PDF enviado a un cliente no cambie retroactivamente si se edita la cotización).

### 3.4 Sin endpoint de conversión Cotización → Factura
`invoices` tiene `quote_id`, lo que sugiere que una factura nace de una cotización aceptada, pero no existe `POST /quotes/{id}/convert-to-invoice`. Sin esto, el usuario tendría que recapturar manualmente todos los ítems en `/invoices`, duplicando datos y contradiciendo el flujo declarado en la sección 1.

**Recomendación:** Agregar el endpoint; debe copiar `quote_items` → `invoice_items` dentro de una transacción y solo permitirse si `quote.status = accepted`.

### 3.5 No hay endpoint para búsqueda global
El frontend define una barra de "Búsqueda global" (sección 31 del doc de frontend) que busca simultáneamente en leads, contactos, empresas, oportunidades, cotizaciones y facturas. El backend no expone ningún `GET /search?q=...` que resuelva esto.

**Recomendación:** Definir un endpoint agregador (`GET /search`) que use `pg_trgm`/`tsvector` (ya mencionado en la sección 15) sobre las tablas relevantes y devuelva resultados tipados con `entity_type`.

### 3.6 Sin tabla ni endpoints de notificaciones internas
El frontend (sección 32) espera notificaciones internas ("Nueva asignación", "Nuevo Lead", "Factura vencida"), pero no existe `notifications` en el esquema ni un endpoint para listarlas/marcarlas como leídas.

**Recomendación:** Agregar tabla `notifications (id, user_id, type, title, body, entity_type, entity_id, read_at, created_at)` y endpoints `GET /notifications`, `POST /notifications/{id}/read`. Evaluar si se requiere push en tiempo real (WebSocket/SSE) desde el MVP o si polling cada N segundos es aceptable inicialmente.

### 3.7 Deduplicación solo contemplada para Leads
La sección 8 define deduplicación de leads por email/teléfono/WhatsApp, pero no hay mención de deduplicación al crear `Contact` o `Company` directamente (fuera del flujo de conversión), ni durante la conversión misma si ya existe un contacto con ese email en otra empresa.

**Recomendación:** Extender la lógica de normalización de teléfono y búsqueda por email también a la creación directa de `contacts` y `companies`, con una advertencia (no bloqueo duro) si se detecta posible duplicado — un CRM que bloquea duro genera fricción cuando el dato coincide por coincidencia.

### 3.8 Sin especificación de paginación/orden estándar
Los filtros de `/leads` están documentados, pero ningún endpoint de listado define parámetros de paginación (`page`, `page_size` o `limit`/`offset`) ni el formato del envelope de respuesta (¿incluye `total`, `total_pages`?). Sin esto, cada desarrollador implementará su propia convención.

**Recomendación:** Definir un estándar único, por ejemplo:
```json
{ "items": [...], "total": 245, "page": 1, "page_size": 25 }
```
y aplicarlo a **todos** los `GET` de listado (`leads`, `contacts`, `companies`, `quotes`, `invoices`, `activities`, `communications`).

### 3.9 Integración de WhatsApp sin mención de la ventana de 24 horas de Meta
La sección 7 asume que se puede enviar un mensaje libre en cualquier momento vía "Buscar contacto / Buscar lead / Crear lead", pero la WhatsApp Business API (Meta) **restringe mensajes de formato libre a una ventana de 24 horas** desde el último mensaje del cliente; fuera de esa ventana se requieren plantillas (`message templates`) pre-aprobadas.

**Recomendación:** Documentar este comportamiento ahora, porque afecta el diseño de la UI de conversaciones (sección 20 del frontend) y del modelo de datos (`communications` debería registrar si el mensaje fue plantilla o texto libre, y calcular si la ventana sigue abierta).

---

## 4. Hallazgos de severidad media 🟡

| # | Observación | Recomendación |
|---|---|---|
| 4.1 | `opportunity_services`, `quote_items` e `invoice_items` duplican estructura sin relación explícita entre sí (¿la cotización copia los servicios de la oportunidad? ¿la factura copia de la cotización?). | Documentar explícitamente la semántica de copia ("snapshot" al momento de creación) para que precios cambiados en `services` no alteren cotizaciones ya emitidas. |
| 4.2 | No se define constraint que asegure que una `Opportunity` tenga `contact_id` **o** `company_id` de forma coherente con `pipeline_type` (b2c/b2b). | Agregar `CHECK constraint` o validación a nivel de servicio. |
| 4.3 | `companies` no tiene `tax_id` marcado `UNIQUE`, pese a que es el identificador natural de una empresa (más confiable que `name` para deduplicar). | Agregar índice único parcial sobre `tax_id` cuando no sea nulo. |
| 4.4 | No hay endpoint de "olvidé mi contraseña" / recuperación de cuenta. | Agregar `POST /auth/forgot-password` y `POST /auth/reset-password` con token de un solo uso y expiración corta. |
| 4.5 | No se especifica dónde ni cómo vive el refresh token (¿cookie httpOnly, tabla de sesiones para revocación?). | Definir explícitamente: refresh token como cookie `httpOnly + Secure + SameSite=Strict`, con tabla `refresh_tokens` para poder revocar sesiones (ej. al desactivar un usuario). |
| 4.6 | No hay endpoint de *health check* / *readiness* para orquestación (Docker/Heroku). | Agregar `GET /health` (liveness) y `GET /health/ready` (verifica conexión a DB). |
| 4.7 | Cumplimiento con la Ley N.º 8968 (Protección de la Persona frente al tratamiento de sus datos personales, Costa Rica) no se menciona, pese a que el sistema almacena datos personales de individuos (leads/contactos). | Agregar sección de cumplimiento: consentimiento de tratamiento de datos en formularios web, derecho de acceso/rectificación/eliminación, política de retención. |
| 4.8 | No hay estrategia de pruebas (unitarias/integración) pese a que existe carpeta `tests/`. | Definir cobertura mínima esperada, uso de fixtures/factories (ej. `factory_boy`), y pruebas de integración contra una base de datos de prueba (contenedor efímero). |

---

## 5. Hallazgos menores / mejoras 🟢

- **CI/CD**: no se menciona pipeline (lint, tests, build de imagen, migraciones automáticas en despliegue). Recomiendo GitHub Actions dado que el resto del ecosistema de Greivin ya usa GitHub.
- **OpenAPI**: FastAPI lo genera automáticamente; vale la pena declarar explícitamente el estándar de documentación de cada endpoint (`summary`, `description`, ejemplos) como requisito de "Definition of Done".
- **Logging estructurado**: no se menciona (ej. `structlog` con correlación de `request_id`), útil para depurar webhooks fallidos.
- **Rate limiting**: mencionado como principio (sección 13) pero sin mecanismo concreto (ej. `slowapi` o un middleware con Redis).
- **Auditoría de lectura**: la tabla `audit_logs` cubre escritura, pero no accesos a datos sensibles (ej. quién vio la información de un contacto). Puede no ser necesario para el MVP, pero vale la pena decidirlo conscientemente y no por omisión.

---

## 6. Priorización recomendada para el MVP

1. **Antes de escribir código:** resolver 2.1 (soft delete), 2.3 (numeración segura), 3.2 (matriz de permisos), 4.1/4.2 (semántica de line items).
2. **Durante el MVP:** 2.2 (usuarios), 2.4 (transacciones en conversión), 3.3/3.4 (PDF y conversión a factura), 3.8 (paginación estándar).
3. **Puede diferirse post-MVP pero debe quedar diseñado (no bloqueante para el core):** 2.5/2.6 (colas y webhooks — solo si se activa WhatsApp/Email en esta fase), 3.5/3.6 (búsqueda global y notificaciones), 3.9 (ventana de 24h de WhatsApp).

Esto es coherente con la propia priorización del documento original (sección 18), solo añadiendo los prerequisitos de integridad de datos que no pueden posponerse sin generar migraciones dolorosas más adelante.
