# CRM Clínica Satori
## Especificación Técnica — Backend REST API

**Versión:** 1.0  
**Backend:** Python + FastAPI  
**Base de Datos:** PostgreSQL  
**ORM:** SQLAlchemy 2.x  
**Migraciones:** Alembic  
**Autenticación:** JWT  
**Arquitectura:** REST API

---

# 1. Objetivo

Desarrollar el backend de un CRM para **Clínica Satori**, orientado a la gestión comercial de servicios de psicología para:

- Individuos / pacientes potenciales (B2C)
- Empresas / organizaciones (B2B)
- Leads provenientes de formularios web
- Leads provenientes de WhatsApp
- Contactos
- Empresas
- Servicios
- Cotizaciones
- Facturas
- Pipeline comercial
- Actividades y seguimiento

El CRM debe permitir administrar el ciclo completo:

```text
Lead
  ↓
Calificación
  ↓
Contacto / Empresa
  ↓
Oportunidad
  ↓
Cotización
  ↓
Venta
  ↓
Factura
  ↓
Servicio
```

---

# 2. Arquitectura

```text
                    ┌──────────────────────┐
                    │   React + Tailwind   │
                    │      Frontend        │
                    └──────────┬───────────┘
                               │ HTTPS / JSON
                               ▼
                    ┌──────────────────────┐
                    │      FastAPI         │
                    │       REST API       │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌────────────┐   ┌──────────────┐  ┌─────────────┐
       │ PostgreSQL │   │ Email/Form   │  │  WhatsApp   │
       │            │   │ Integration  │  │ Integration │
       └────────────┘   └──────────────┘  └─────────────┘
```

---

# 3. Estructura del proyecto

```text
backend/
│
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── database.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── lead.py
│   │   ├── contact.py
│   │   ├── company.py
│   │   ├── service.py
│   │   ├── pipeline.py
│   │   ├── opportunity.py
│   │   ├── quote.py
│   │   ├── invoice.py
│   │   ├── activity.py
│   │   └── communication.py
│   │
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── lead.py
│   │   ├── contact.py
│   │   ├── company.py
│   │   ├── service.py
│   │   ├── pipeline.py
│   │   ├── opportunity.py
│   │   ├── quote.py
│   │   ├── invoice.py
│   │   ├── activity.py
│   │   └── communication.py
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── leads.py
│   │       ├── contacts.py
│   │       ├── companies.py
│   │       ├── services.py
│   │       ├── pipelines.py
│   │       ├── opportunities.py
│   │       ├── quotes.py
│   │       ├── invoices.py
│   │       ├── activities.py
│   │       └── communications.py
│   │
│   ├── services/
│   │   ├── lead_service.py
│   │   ├── quote_service.py
│   │   ├── invoice_service.py
│   │   ├── email_service.py
│   │   └── whatsapp_service.py
│   │
│   └── repositories/
│       └── ...
│
├── migrations/
│
├── tests/
│
├── requirements.txt
├── alembic.ini
└── .env
```

---

# 4. Entidades principales

```text
User
 │
 ├── Lead
 ├── Contact
 ├── Company
 ├── Opportunity
 ├── Quote
 ├── Invoice
 └── Activity

Lead
 │
 └── conversion
      ├── Contact
      └── Company

Company
 │
 └── Contacts

Pipeline
 │
 └── PipelineStage
      │
      └── Opportunities

Opportunity
 │
 ├── Contact / Company
 ├── Services
 ├── Quote
 └── Activities

Quote
 │
 └── QuoteItems
      │
      └── Services

Invoice
 │
 └── InvoiceItems
      │
      └── Services
```

---

# 5. PostgreSQL Schema

## 5.1 users

```sql
users
-----
id UUID PK
first_name VARCHAR(100)
last_name VARCHAR(100)
email VARCHAR(255) UNIQUE
password_hash VARCHAR(255)
role VARCHAR(50)
is_active BOOLEAN
created_at TIMESTAMP
updated_at TIMESTAMP
```

Roles iniciales:

```text
admin
manager
sales
therapist
accounting
```

---

# 5.2 leads

Un Lead representa una persona o empresa que todavía no ha sido convertida.

```sql
leads
-----
id UUID PK

lead_type VARCHAR(20)
first_name VARCHAR(100)
last_name VARCHAR(100)

company_name VARCHAR(255)

email VARCHAR(255)
phone VARCHAR(50)
whatsapp VARCHAR(50)

source VARCHAR(50)
source_reference VARCHAR(255)

status VARCHAR(50)
score INTEGER

message TEXT

assigned_to UUID FK users.id

created_at TIMESTAMP
updated_at TIMESTAMP
converted_at TIMESTAMP
```

### lead_type

```text
individual
company
```

### source

```text
website
email
whatsapp
facebook
instagram
linkedin
referral
phone
other
```

### status

```text
new
contacted
qualified
unqualified
converted
lost
```

---

# 5.3 contacts

```sql
contacts
--------
id UUID PK

first_name VARCHAR(100)
last_name VARCHAR(100)

email VARCHAR(255)
phone VARCHAR(50)
whatsapp VARCHAR(50)

job_title VARCHAR(150)

company_id UUID FK companies.id

lead_id UUID FK leads.id

notes TEXT

created_at TIMESTAMP
updated_at TIMESTAMP
```

Un contacto puede representar:

- Cliente individual
- Persona de contacto de una empresa
- Persona responsable de RRHH
- Gerente
- Encargado de bienestar empresarial

---

# 5.4 companies

```sql
companies
---------
id UUID PK

name VARCHAR(255)

legal_name VARCHAR(255)
tax_id VARCHAR(100)

industry VARCHAR(150)

email VARCHAR(255)
phone VARCHAR(50)
website VARCHAR(255)

address TEXT
city VARCHAR(100)
country VARCHAR(100)

notes TEXT

created_at TIMESTAMP
updated_at TIMESTAMP
```

---

# 5.5 services

Catálogo de servicios de Clínica Satori.

```sql
services
--------
id UUID PK

name VARCHAR(255)
code VARCHAR(50) UNIQUE

description TEXT

service_type VARCHAR(50)

price NUMERIC(12,2)
currency VARCHAR(3)

billing_type VARCHAR(50)

is_active BOOLEAN

created_at TIMESTAMP
updated_at TIMESTAMP
```

### service_type

```text
individual
corporate
workshop
consulting
therapy
assessment
other
```

### billing_type

```text
one_time
hourly
session
monthly
custom
```

---

# 5.6 pipelines

```sql
pipelines
---------
id UUID PK

name VARCHAR(150)
description TEXT

pipeline_type VARCHAR(50)

is_default BOOLEAN
is_active BOOLEAN

created_at TIMESTAMP
updated_at TIMESTAMP
```

Tipos:

```text
b2c
b2b
```

---

# 5.7 pipeline_stages

```sql
pipeline_stages
---------------
id UUID PK

pipeline_id UUID FK pipelines.id

name VARCHAR(150)

stage_order INTEGER

probability INTEGER

color VARCHAR(20)

is_won BOOLEAN
is_lost BOOLEAN

created_at TIMESTAMP
```

Pipeline B2C sugerido:

```text
Nuevo Lead
Contacto Inicial
Evaluación de Necesidad
Propuesta
Seguimiento
Ganado
Perdido
```

Pipeline B2B:

```text
Lead Empresarial
Contacto
Reunión
Diagnóstico
Propuesta
Negociación
Cierre
Ganado
Perdido
```

---

# 5.8 opportunities

```sql
opportunities
-------------
id UUID PK

name VARCHAR(255)

pipeline_id UUID FK pipelines.id
stage_id UUID FK pipeline_stages.id

lead_id UUID FK leads.id

contact_id UUID FK contacts.id
company_id UUID FK companies.id

expected_value NUMERIC(12,2)
currency VARCHAR(3)

probability INTEGER

expected_close_date DATE

status VARCHAR(50)

assigned_to UUID FK users.id

notes TEXT

created_at TIMESTAMP
updated_at TIMESTAMP
closed_at TIMESTAMP
```

### status

```text
open
won
lost
```

---

# 5.9 opportunity_services

```sql
opportunity_services
--------------------
id UUID PK

opportunity_id UUID FK opportunities.id
service_id UUID FK services.id

quantity NUMERIC(10,2)
unit_price NUMERIC(12,2)

discount NUMERIC(12,2)

total NUMERIC(12,2)
```

---

# 5.10 quotes

```sql
quotes
------
id UUID PK

quote_number VARCHAR(50) UNIQUE

opportunity_id UUID FK opportunities.id

contact_id UUID FK contacts.id
company_id UUID FK companies.id

status VARCHAR(50)

subtotal NUMERIC(12,2)
discount NUMERIC(12,2)
tax NUMERIC(12,2)
total NUMERIC(12,2)

currency VARCHAR(3)

valid_until DATE

notes TEXT

created_by UUID FK users.id

created_at TIMESTAMP
updated_at TIMESTAMP
sent_at TIMESTAMP
accepted_at TIMESTAMP
```

Estados:

```text
draft
sent
viewed
accepted
rejected
expired
cancelled
```

---

# 5.11 quote_items

```sql
quote_items
-----------
id UUID PK

quote_id UUID FK quotes.id
service_id UUID FK services.id

description TEXT

quantity NUMERIC(10,2)
unit_price NUMERIC(12,2)

discount NUMERIC(12,2)
tax NUMERIC(12,2)

total NUMERIC(12,2)
```

---

# 5.12 invoices

```sql
invoices
--------
id UUID PK

invoice_number VARCHAR(50) UNIQUE

quote_id UUID FK quotes.id
opportunity_id UUID FK opportunities.id

contact_id UUID FK contacts.id
company_id UUID FK companies.id

status VARCHAR(50)

subtotal NUMERIC(12,2)
discount NUMERIC(12,2)
tax NUMERIC(12,2)
total NUMERIC(12,2)

currency VARCHAR(3)

issue_date DATE
due_date DATE
paid_date DATE

notes TEXT

created_by UUID FK users.id

created_at TIMESTAMP
updated_at TIMESTAMP
```

Estados:

```text
draft
issued
sent
partial
paid
overdue
cancelled
```

---

# 5.13 invoice_items

```sql
invoice_items
-------------
id UUID PK

invoice_id UUID FK invoices.id
service_id UUID FK services.id

description TEXT

quantity NUMERIC(10,2)
unit_price NUMERIC(12,2)

discount NUMERIC(12,2)
tax NUMERIC(12,2)

total NUMERIC(12,2)
```

---

# 5.14 activities

Sistema de seguimiento comercial.

```sql
activities
----------
id UUID PK

type VARCHAR(50)

subject VARCHAR(255)
description TEXT

lead_id UUID FK leads.id
contact_id UUID FK contacts.id
company_id UUID FK companies.id
opportunity_id UUID FK opportunities.id

assigned_to UUID FK users.id

status VARCHAR(50)

due_date TIMESTAMP
completed_at TIMESTAMP

created_at TIMESTAMP
```

Tipos:

```text
call
email
whatsapp
meeting
task
note
follow_up
```

---

# 5.15 communications

Registro de comunicaciones externas.

```sql
communications
--------------
id UUID PK

channel VARCHAR(30)

direction VARCHAR(20)

lead_id UUID FK leads.id
contact_id UUID FK contacts.id
company_id UUID FK companies.id

external_id VARCHAR(255)

from_address VARCHAR(255)
to_address VARCHAR(255)

subject VARCHAR(255)

message TEXT

status VARCHAR(50)

created_at TIMESTAMP
```

### channel

```text
email
whatsapp
phone
web
```

### direction

```text
inbound
outbound
```

---

# 6. Integración de Email

El sistema debe poder recibir leads provenientes de formularios de contacto.

Flujo:

```text
Website Form
     │
     ▼
Email Provider
     │
     ▼
FastAPI Email/Webhook
     │
     ▼
Lead Parser
     │
     ▼
Lead
     │
     ▼
Pipeline
```

El parser debe intentar identificar:

```text
Nombre
Apellido
Empresa
Email
Teléfono
WhatsApp
Servicio solicitado
Mensaje
Origen
```

El sistema debe evitar crear duplicados mediante:

```text
email
phone
whatsapp
```

---

# 7. Integración WhatsApp

La integración debe estar preparada para utilizar un proveedor oficial de WhatsApp Business API.

Flujo:

```text
WhatsApp
    │
    ▼
Webhook
    │
    ▼
FastAPI
    │
    ├── Buscar contacto
    │
    ├── Buscar lead
    │
    └── Crear lead
    │
    ▼
CRM
```

Información mínima:

```text
phone
name
message
timestamp
external_message_id
```

Cada mensaje debe almacenarse en `communications`.

---

# 8. Lead Deduplication

Antes de crear un Lead:

```text
1. Buscar por email
2. Buscar por teléfono
3. Buscar por WhatsApp
4. Si existe → actualizar Lead
5. Si no existe → crear Lead
```

Debe existir un sistema de normalización de teléfonos.

Ejemplo:

```text
+506 8888-8888
50688888888
88888888
```

Deben normalizarse antes de comparar.

---

# 9. Conversión de Lead

Endpoint:

```http
POST /api/v1/leads/{lead_id}/convert
```

La conversión puede generar:

```text
Lead
 │
 ├── Contact
 │
 ├── Company (si B2B)
 │
 └── Opportunity
```

Ejemplo B2C:

```text
Lead
 ↓
Contact
 ↓
Opportunity
```

Ejemplo B2B:

```text
Lead
 ↓
Company
 ├── Contact
 ↓
Opportunity
```

---

# 10. REST API

Base:

```text
/api/v1
```

## Authentication

```http
POST /auth/login
POST /auth/refresh
GET  /auth/me
```

---

## Leads

```http
GET    /leads
POST   /leads
GET    /leads/{id}
PUT    /leads/{id}
DELETE /leads/{id}

POST   /leads/{id}/convert
POST   /leads/{id}/assign
```

Filtros:

```text
status
source
lead_type
assigned_to
created_from
created_to
search
```

---

## Contacts

```http
GET    /contacts
POST   /contacts
GET    /contacts/{id}
PUT    /contacts/{id}
DELETE /contacts/{id}
```

---

## Companies

```http
GET    /companies
POST   /companies
GET    /companies/{id}
PUT    /companies/{id}
DELETE /companies/{id}
```

---

## Services

```http
GET    /services
POST   /services
GET    /services/{id}
PUT    /services/{id}
DELETE /services/{id}
```

---

## Pipelines

```http
GET    /pipelines
POST   /pipelines

GET    /pipelines/{id}
PUT    /pipelines/{id}

GET    /pipelines/{id}/stages
POST   /pipelines/{id}/stages
```

---

## Opportunities

```http
GET    /opportunities
POST   /opportunities
GET    /opportunities/{id}
PUT    /opportunities/{id}
DELETE /opportunities/{id}

POST   /opportunities/{id}/move
POST   /opportunities/{id}/won
POST   /opportunities/{id}/lost
```

---

## Quotes

```http
GET    /quotes
POST   /quotes
GET    /quotes/{id}
PUT    /quotes/{id}
DELETE /quotes/{id}

POST   /quotes/{id}/send
POST   /quotes/{id}/accept
POST   /quotes/{id}/reject
```

---

## Invoices

```http
GET    /invoices
POST   /invoices
GET    /invoices/{id}
PUT    /invoices/{id}

POST   /invoices/{id}/send
POST   /invoices/{id}/mark-paid
POST   /invoices/{id}/cancel
```

---

## Activities

```http
GET    /activities
POST   /activities
GET    /activities/{id}
PUT    /activities/{id}
DELETE /activities/{id}

POST   /activities/{id}/complete
```

---

## Communications

```http
GET /communications
GET /communications/{id}
```

Los registros de comunicaciones no deberían ser editables por usuarios normales.

---

# 11. Webhooks

## Email

```http
POST /webhooks/email
```

## WhatsApp

```http
POST /webhooks/whatsapp
```

Los webhooks deben:

- Validar autenticidad
- Registrar evento
- Evitar duplicados
- Procesar mensaje
- Crear/actualizar Lead
- Registrar Communication
- Generar Activity cuando corresponda

---

# 12. Dashboard API

```http
GET /dashboard
```

Respuesta conceptual:

```json
{
  "leads": {
    "total": 120,
    "new": 25,
    "qualified": 38,
    "converted": 42
  },
  "opportunities": {
    "open": 31,
    "won": 15,
    "lost": 8,
    "pipeline_value": 245000
  },
  "quotes": {
    "pending": 12,
    "accepted": 8,
    "total_value": 95000
  },
  "invoices": {
    "pending": 10,
    "overdue": 3,
    "paid": 27
  }
}
```

---

# 13. Seguridad

Implementar:

```text
JWT Authentication
Password Hashing
Role Based Access Control
CORS
Rate Limiting
Input Validation
SQL Injection Protection
Webhook Signature Validation
Audit Logging
```

Los datos relacionados con clientes deben considerarse confidenciales.

El sistema debe aplicar el principio de:

```text
Least Privilege
```

---

# 14. Auditoría

Agregar una tabla:

```sql
audit_logs
----------
id UUID PK

user_id UUID
action VARCHAR(100)

entity_type VARCHAR(100)
entity_id UUID

old_data JSONB
new_data JSONB

ip_address VARCHAR(50)

created_at TIMESTAMP
```

Registrar especialmente:

```text
CREATE
UPDATE
DELETE
CONVERT
SEND_QUOTE
ACCEPT_QUOTE
CREATE_INVOICE
MARK_PAID
```

---

# 15. Índices PostgreSQL

Índices recomendados:

```sql
leads(email)
leads(phone)
leads(whatsapp)
leads(status)
leads(source)

contacts(email)
contacts(phone)

companies(name)

opportunities(status)
opportunities(stage_id)
opportunities(company_id)
opportunities(contact_id)

quotes(quote_number)
quotes(status)

invoices(invoice_number)
invoices(status)

activities(due_date)

communications(external_id)
communications(channel)
```

Para búsquedas de texto:

```text
PostgreSQL Full Text Search
```

o posteriormente:

```text
pg_trgm
```

---

# 16. Variables de entorno

```env
APP_NAME=Clinica Satori CRM
APP_ENV=development

DATABASE_URL=postgresql+asyncpg://...

SECRET_KEY=...
JWT_ALGORITHM=HS256

CORS_ORIGINS=http://localhost:3000

EMAIL_PROVIDER=...
EMAIL_API_KEY=...

WHATSAPP_PROVIDER=...
WHATSAPP_API_KEY=...
WHATSAPP_VERIFY_TOKEN=...
```

---

# 17. Docker

Desarrollo:

```text
docker-compose.yml

services:

  api:
    FastAPI

  postgres:
    PostgreSQL

  redis:
    Redis
```

Redis es opcional para el MVP, pero recomendable si posteriormente se incorporan:

- Jobs
- Emails
- WhatsApp
- Notificaciones
- Procesamiento asíncrono

---

# 18. Principios del MVP

La primera versión debe concentrarse en:

```text
Authentication
        ↓
Leads
        ↓
Contacts
        ↓
Companies
        ↓
Services
        ↓
Pipeline
        ↓
Opportunities
        ↓
Quotes
        ↓
Invoices
        ↓
Activities
        ↓
Email / WhatsApp
```

Evitar inicialmente:

```text
Contabilidad completa
Expediente clínico
Historia clínica
Agenda médica compleja
Pagos online
Automatizaciones avanzadas
IA
Marketing automation
```

Estos componentes pueden incorporarse posteriormente sin modificar la estructura principal del CRM.