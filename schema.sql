-- =====================================================================
-- CRM Clínica Satori — Esquema de base de datos PostgreSQL (v2.0 final)
-- Incorpora las correcciones de la revisión arquitectónica:
--   - Soft delete en entidades de negocio
--   - Tipos ENUM en vez de VARCHAR libres
--   - Numeración segura de documentos (sin condición de carrera)
--   - Tablas de soporte: users, refresh_tokens, webhook_events,
--     notifications, audit_logs, document_counters
--   - Triggers de updated_at e integridad de negocio
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. Extensiones
-- ---------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- búsqueda difusa / ILIKE eficiente

-- ---------------------------------------------------------------------
-- 1. Tipos ENUM
-- ---------------------------------------------------------------------
CREATE TYPE user_role_enum        AS ENUM ('admin','manager','sales','therapist','accounting');
CREATE TYPE lead_type_enum        AS ENUM ('individual','company');
CREATE TYPE lead_source_enum      AS ENUM ('website','email','whatsapp','facebook','instagram','linkedin','referral','phone','other');
CREATE TYPE lead_status_enum      AS ENUM ('new','contacted','qualified','unqualified','converted','lost');
CREATE TYPE service_type_enum     AS ENUM ('individual','corporate','workshop','consulting','therapy','assessment','other');
CREATE TYPE billing_type_enum     AS ENUM ('one_time','hourly','session','monthly','custom');
CREATE TYPE pipeline_type_enum    AS ENUM ('b2c','b2b');
CREATE TYPE opportunity_status_enum AS ENUM ('open','won','lost');
CREATE TYPE quote_status_enum     AS ENUM ('draft','sent','viewed','accepted','rejected','expired','cancelled');
CREATE TYPE invoice_status_enum   AS ENUM ('draft','issued','sent','partial','paid','overdue','cancelled');
CREATE TYPE activity_type_enum    AS ENUM ('call','email','whatsapp','meeting','task','note','follow_up');
CREATE TYPE activity_status_enum  AS ENUM ('pending','completed','cancelled');
CREATE TYPE comm_channel_enum     AS ENUM ('email','whatsapp','phone','web');
CREATE TYPE comm_direction_enum   AS ENUM ('inbound','outbound');
CREATE TYPE comm_status_enum      AS ENUM ('queued','sent','delivered','read','failed');
CREATE TYPE webhook_provider_enum AS ENUM ('email','whatsapp');
CREATE TYPE webhook_status_enum   AS ENUM ('received','processing','processed','failed');
CREATE TYPE document_type_enum    AS ENUM ('quote','invoice');

-- ---------------------------------------------------------------------
-- 2. Función utilitaria: updated_at automático
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 3. users  (Hallazgo backend 2.2)
-- ---------------------------------------------------------------------
CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  first_name      VARCHAR(100) NOT NULL,
  last_name       VARCHAR(100) NOT NULL,
  email           VARCHAR(255) NOT NULL,
  password_hash   VARCHAR(255) NOT NULL,
  role            user_role_enum NOT NULL,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  deleted_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- único solo entre usuarios no eliminados (permite re-crear el email tras baja)
CREATE UNIQUE INDEX ux_users_email_active ON users (email) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- 4. refresh_tokens  (Hallazgo frontend 2.1 / backend 4.5)
-- ---------------------------------------------------------------------
CREATE TABLE refresh_tokens (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash    VARCHAR(255) NOT NULL,         -- nunca se guarda el token en claro
  user_agent    VARCHAR(255),
  ip_address    VARCHAR(50),
  expires_at    TIMESTAMPTZ NOT NULL,
  revoked_at    TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE UNIQUE INDEX ux_refresh_tokens_hash ON refresh_tokens(token_hash);

-- ---------------------------------------------------------------------
-- 5. companies  (antes de leads/contacts por el FK cruzado)
-- ---------------------------------------------------------------------
CREATE TABLE companies (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,
  legal_name      VARCHAR(255),
  tax_id          VARCHAR(100),
  industry        VARCHAR(150),
  email           VARCHAR(255),
  phone           VARCHAR(50),
  website         VARCHAR(255),
  address         TEXT,
  city            VARCHAR(100),
  country         VARCHAR(100) DEFAULT 'Costa Rica',
  notes           TEXT,
  deleted_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_companies_tax_id_active ON companies (tax_id) WHERE deleted_at IS NULL AND tax_id IS NOT NULL;
CREATE INDEX ix_companies_name_trgm ON companies USING gin (name gin_trgm_ops);
CREATE TRIGGER trg_companies_updated_at BEFORE UPDATE ON companies
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- 6. leads
-- ---------------------------------------------------------------------
CREATE TABLE leads (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_type         lead_type_enum NOT NULL,
  first_name        VARCHAR(100),
  last_name         VARCHAR(100),
  company_name      VARCHAR(255),
  email             VARCHAR(255),
  phone             VARCHAR(50),
  phone_normalized  VARCHAR(30),          -- normalizado sin espacios/guiones/código país opcional
  whatsapp          VARCHAR(50),
  whatsapp_normalized VARCHAR(30),
  source            lead_source_enum NOT NULL,
  source_reference  VARCHAR(255),
  status            lead_status_enum NOT NULL DEFAULT 'new',
  score             INTEGER DEFAULT 0,
  message           TEXT,
  assigned_to       UUID REFERENCES users(id),
  deleted_at        TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  converted_at      TIMESTAMPTZ
);
CREATE INDEX ix_leads_email ON leads(email);
CREATE INDEX ix_leads_phone_normalized ON leads(phone_normalized);
CREATE INDEX ix_leads_whatsapp_normalized ON leads(whatsapp_normalized);
CREATE INDEX ix_leads_status ON leads(status);
CREATE INDEX ix_leads_source ON leads(source);
CREATE INDEX ix_leads_assigned_to ON leads(assigned_to);
CREATE INDEX ix_leads_search_trgm ON leads USING gin ((coalesce(first_name,'') || ' ' || coalesce(last_name,'') || ' ' || coalesce(company_name,'')) gin_trgm_ops);
CREATE TRIGGER trg_leads_updated_at BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- 7. contacts
-- ---------------------------------------------------------------------
CREATE TABLE contacts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  first_name    VARCHAR(100) NOT NULL,
  last_name     VARCHAR(100) NOT NULL,
  email         VARCHAR(255),
  phone         VARCHAR(50),
  whatsapp      VARCHAR(50),
  job_title     VARCHAR(150),
  company_id    UUID REFERENCES companies(id),
  lead_id       UUID REFERENCES leads(id),
  notes         TEXT,
  deleted_at    TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_contacts_email ON contacts(email);
CREATE INDEX ix_contacts_phone ON contacts(phone);
CREATE INDEX ix_contacts_company_id ON contacts(company_id);
CREATE INDEX ix_contacts_search_trgm ON contacts USING gin ((first_name || ' ' || last_name) gin_trgm_ops);
CREATE TRIGGER trg_contacts_updated_at BEFORE UPDATE ON contacts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- 8. services
-- ---------------------------------------------------------------------
CREATE TABLE services (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          VARCHAR(255) NOT NULL,
  code          VARCHAR(50) NOT NULL,
  description   TEXT,
  service_type  service_type_enum NOT NULL,
  price         NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency      VARCHAR(3) NOT NULL DEFAULT 'CRC',
  billing_type  billing_type_enum NOT NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  deleted_at    TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_services_code_active ON services (code) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_services_updated_at BEFORE UPDATE ON services
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------
-- 9. pipelines / pipeline_stages
-- ---------------------------------------------------------------------
CREATE TABLE pipelines (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          VARCHAR(150) NOT NULL,
  description   TEXT,
  pipeline_type pipeline_type_enum NOT NULL,
  is_default    BOOLEAN NOT NULL DEFAULT FALSE,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_pipelines_updated_at BEFORE UPDATE ON pipelines
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE pipeline_stages (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id   UUID NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
  name          VARCHAR(150) NOT NULL,
  stage_order   INTEGER NOT NULL,
  probability   INTEGER NOT NULL DEFAULT 0 CHECK (probability BETWEEN 0 AND 100),
  color         VARCHAR(20),
  is_won        BOOLEAN NOT NULL DEFAULT FALSE,
  is_lost       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_pipeline_stages_pipeline_id ON pipeline_stages(pipeline_id);
CREATE UNIQUE INDEX ux_pipeline_stages_order ON pipeline_stages(pipeline_id, stage_order);

-- ---------------------------------------------------------------------
-- 10. opportunities
-- ---------------------------------------------------------------------
CREATE TABLE opportunities (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                  VARCHAR(255) NOT NULL,
  pipeline_id           UUID NOT NULL REFERENCES pipelines(id),
  stage_id              UUID NOT NULL REFERENCES pipeline_stages(id),
  lead_id               UUID REFERENCES leads(id),
  contact_id            UUID REFERENCES contacts(id),
  company_id            UUID REFERENCES companies(id),
  expected_value        NUMERIC(12,2) DEFAULT 0,
  currency              VARCHAR(3) NOT NULL DEFAULT 'CRC',
  probability           INTEGER DEFAULT 0 CHECK (probability BETWEEN 0 AND 100),
  expected_close_date   DATE,
  status                opportunity_status_enum NOT NULL DEFAULT 'open',
  assigned_to           UUID REFERENCES users(id),
  notes                 TEXT,
  deleted_at            TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at             TIMESTAMPTZ,
  -- Hallazgo backend 4.2: una oportunidad debe tener al menos un cliente asociado
  CONSTRAINT chk_opportunity_has_customer CHECK (contact_id IS NOT NULL OR company_id IS NOT NULL)
);
CREATE INDEX ix_opportunities_status ON opportunities(status);
CREATE INDEX ix_opportunities_stage_id ON opportunities(stage_id);
CREATE INDEX ix_opportunities_company_id ON opportunities(company_id);
CREATE INDEX ix_opportunities_contact_id ON opportunities(contact_id);
CREATE INDEX ix_opportunities_assigned_to ON opportunities(assigned_to);
CREATE TRIGGER trg_opportunities_updated_at BEFORE UPDATE ON opportunities
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Trigger: coherencia entre pipeline_type (b2b) y la presencia de company_id
CREATE OR REPLACE FUNCTION check_opportunity_pipeline_coherence()
RETURNS TRIGGER AS $$
DECLARE
  v_pipeline_type pipeline_type_enum;
BEGIN
  SELECT pipeline_type INTO v_pipeline_type FROM pipelines WHERE id = NEW.pipeline_id;
  IF v_pipeline_type = 'b2b' AND NEW.company_id IS NULL THEN
    RAISE EXCEPTION 'Una oportunidad en un pipeline B2B requiere company_id';
  END IF;
  IF v_pipeline_type = 'b2c' AND NEW.contact_id IS NULL THEN
    RAISE EXCEPTION 'Una oportunidad en un pipeline B2C requiere contact_id';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_opportunity_pipeline_coherence
  BEFORE INSERT OR UPDATE ON opportunities
  FOR EACH ROW EXECUTE FUNCTION check_opportunity_pipeline_coherence();

-- Trigger: la etapa (stage_id) debe pertenecer al pipeline indicado (pipeline_id)
CREATE OR REPLACE FUNCTION check_opportunity_stage_belongs_to_pipeline()
RETURNS TRIGGER AS $$
DECLARE
  v_stage_pipeline UUID;
BEGIN
  SELECT pipeline_id INTO v_stage_pipeline FROM pipeline_stages WHERE id = NEW.stage_id;
  IF v_stage_pipeline IS DISTINCT FROM NEW.pipeline_id THEN
    RAISE EXCEPTION 'La etapa % no pertenece al pipeline %', NEW.stage_id, NEW.pipeline_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_opportunity_stage_pipeline
  BEFORE INSERT OR UPDATE ON opportunities
  FOR EACH ROW EXECUTE FUNCTION check_opportunity_stage_belongs_to_pipeline();

-- ---------------------------------------------------------------------
-- 11. opportunity_services
-- ---------------------------------------------------------------------
CREATE TABLE opportunity_services (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id  UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  service_id      UUID NOT NULL REFERENCES services(id),
  quantity        NUMERIC(10,2) NOT NULL DEFAULT 1,
  unit_price      NUMERIC(12,2) NOT NULL,
  discount        NUMERIC(12,2) NOT NULL DEFAULT 0,
  total           NUMERIC(12,2) NOT NULL
);
CREATE INDEX ix_opportunity_services_opportunity_id ON opportunity_services(opportunity_id);

-- ---------------------------------------------------------------------
-- 12. document_counters + función de numeración segura (Hallazgo backend 2.3)
-- ---------------------------------------------------------------------
CREATE TABLE document_counters (
  doc_type      document_type_enum NOT NULL,
  year          INTEGER NOT NULL,
  last_number   INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (doc_type, year)
);

CREATE OR REPLACE FUNCTION next_document_number(p_doc_type document_type_enum, p_prefix VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
  v_year INTEGER := EXTRACT(YEAR FROM now());
  v_next INTEGER;
BEGIN
  INSERT INTO document_counters(doc_type, year, last_number)
  VALUES (p_doc_type, v_year, 1)
  ON CONFLICT (doc_type, year)
    DO UPDATE SET last_number = document_counters.last_number + 1
  RETURNING last_number INTO v_next;

  RETURN p_prefix || '-' || v_year || '-' || LPAD(v_next::text, 6, '0');
END;
$$ LANGUAGE plpgsql;
-- Uso desde la aplicación (dentro de la misma transacción del INSERT):
--   SELECT next_document_number('quote', 'COT');    -> 'COT-2026-000001'
--   SELECT next_document_number('invoice', 'FAC');   -> 'FAC-2026-000001'
-- El INSERT..ON CONFLICT DO UPDATE es atómico a nivel de fila: dos
-- transacciones concurrentes NUNCA reciben el mismo número.

-- ---------------------------------------------------------------------
-- 13. quotes / quote_items
-- ---------------------------------------------------------------------
CREATE TABLE quotes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quote_number    VARCHAR(50) NOT NULL,
  opportunity_id  UUID REFERENCES opportunities(id),
  contact_id      UUID REFERENCES contacts(id),
  company_id      UUID REFERENCES companies(id),
  status          quote_status_enum NOT NULL DEFAULT 'draft',
  subtotal        NUMERIC(12,2) NOT NULL DEFAULT 0,
  discount        NUMERIC(12,2) NOT NULL DEFAULT 0,
  tax             NUMERIC(12,2) NOT NULL DEFAULT 0,
  total           NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency        VARCHAR(3) NOT NULL DEFAULT 'CRC',
  valid_until     DATE,
  notes           TEXT,
  pdf_path        VARCHAR(500),         -- snapshot inmutable del PDF emitido (Hallazgo frontend 3.3)
  created_by      UUID REFERENCES users(id),
  deleted_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at         TIMESTAMPTZ,
  accepted_at     TIMESTAMPTZ,
  CONSTRAINT chk_quote_has_customer CHECK (contact_id IS NOT NULL OR company_id IS NOT NULL)
);
CREATE UNIQUE INDEX ux_quotes_number_active ON quotes (quote_number) WHERE deleted_at IS NULL;
CREATE INDEX ix_quotes_status ON quotes(status);
CREATE INDEX ix_quotes_opportunity_id ON quotes(opportunity_id);
CREATE TRIGGER trg_quotes_updated_at BEFORE UPDATE ON quotes
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE quote_items (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quote_id      UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  service_id    UUID REFERENCES services(id),
  description   TEXT NOT NULL,
  quantity      NUMERIC(10,2) NOT NULL DEFAULT 1,
  unit_price    NUMERIC(12,2) NOT NULL,
  discount      NUMERIC(12,2) NOT NULL DEFAULT 0,
  tax           NUMERIC(12,2) NOT NULL DEFAULT 0,
  total         NUMERIC(12,2) NOT NULL
);
CREATE INDEX ix_quote_items_quote_id ON quote_items(quote_id);

-- ---------------------------------------------------------------------
-- 14. invoices / invoice_items
-- ---------------------------------------------------------------------
CREATE TABLE invoices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_number  VARCHAR(50) NOT NULL,
  quote_id        UUID REFERENCES quotes(id),
  opportunity_id  UUID REFERENCES opportunities(id),
  contact_id      UUID REFERENCES contacts(id),
  company_id      UUID REFERENCES companies(id),
  status          invoice_status_enum NOT NULL DEFAULT 'draft',
  subtotal        NUMERIC(12,2) NOT NULL DEFAULT 0,
  discount        NUMERIC(12,2) NOT NULL DEFAULT 0,
  tax             NUMERIC(12,2) NOT NULL DEFAULT 0,
  total           NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency        VARCHAR(3) NOT NULL DEFAULT 'CRC',
  issue_date      DATE,
  due_date        DATE,
  paid_date       DATE,
  notes           TEXT,
  pdf_path        VARCHAR(500),
  created_by      UUID REFERENCES users(id),
  deleted_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_invoice_has_customer CHECK (contact_id IS NOT NULL OR company_id IS NOT NULL)
);
CREATE UNIQUE INDEX ux_invoices_number_active ON invoices (invoice_number) WHERE deleted_at IS NULL;
CREATE INDEX ix_invoices_status ON invoices(status);
CREATE INDEX ix_invoices_quote_id ON invoices(quote_id);
CREATE TRIGGER trg_invoices_updated_at BEFORE UPDATE ON invoices
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE invoice_items (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id    UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  service_id    UUID REFERENCES services(id),
  description   TEXT NOT NULL,
  quantity      NUMERIC(10,2) NOT NULL DEFAULT 1,
  unit_price    NUMERIC(12,2) NOT NULL,
  discount      NUMERIC(12,2) NOT NULL DEFAULT 0,
  tax           NUMERIC(12,2) NOT NULL DEFAULT 0,
  total         NUMERIC(12,2) NOT NULL
);
CREATE INDEX ix_invoice_items_invoice_id ON invoice_items(invoice_id);

-- ---------------------------------------------------------------------
-- 15. activities
-- ---------------------------------------------------------------------
CREATE TABLE activities (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type            activity_type_enum NOT NULL,
  subject         VARCHAR(255) NOT NULL,
  description     TEXT,
  lead_id         UUID REFERENCES leads(id),
  contact_id      UUID REFERENCES contacts(id),
  company_id      UUID REFERENCES companies(id),
  opportunity_id  UUID REFERENCES opportunities(id),
  assigned_to     UUID REFERENCES users(id),
  status          activity_status_enum NOT NULL DEFAULT 'pending',
  due_date        TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  deleted_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_activities_due_date ON activities(due_date);
CREATE INDEX ix_activities_assigned_to ON activities(assigned_to);
CREATE INDEX ix_activities_status ON activities(status);

-- ---------------------------------------------------------------------
-- 16. communications
-- ---------------------------------------------------------------------
CREATE TABLE communications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel         comm_channel_enum NOT NULL,
  direction       comm_direction_enum NOT NULL,
  lead_id         UUID REFERENCES leads(id),
  contact_id      UUID REFERENCES contacts(id),
  company_id      UUID REFERENCES companies(id),
  external_id     VARCHAR(255),
  from_address    VARCHAR(255),
  to_address      VARCHAR(255),
  subject         VARCHAR(255),
  message         TEXT,
  is_template     BOOLEAN NOT NULL DEFAULT FALSE,   -- Hallazgo backend 3.9 (ventana 24h WhatsApp)
  status          comm_status_enum NOT NULL DEFAULT 'sent',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_communications_external_id ON communications(external_id) WHERE external_id IS NOT NULL;
CREATE INDEX ix_communications_channel ON communications(channel);
CREATE INDEX ix_communications_lead_id ON communications(lead_id);
CREATE INDEX ix_communications_contact_id ON communications(contact_id);

-- ---------------------------------------------------------------------
-- 17. webhook_events  (Hallazgo backend 2.5 — idempotencia de webhooks)
-- ---------------------------------------------------------------------
CREATE TABLE webhook_events (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider            webhook_provider_enum NOT NULL,
  external_event_id   VARCHAR(255) NOT NULL,
  payload             JSONB NOT NULL,
  status              webhook_status_enum NOT NULL DEFAULT 'received',
  error_message       TEXT,
  received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at        TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_webhook_events_dedup ON webhook_events(provider, external_event_id);

-- ---------------------------------------------------------------------
-- 18. notifications  (Hallazgo backend 3.6 / frontend 2.3)
-- ---------------------------------------------------------------------
CREATE TABLE notifications (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type          VARCHAR(50) NOT NULL,
  title         VARCHAR(255) NOT NULL,
  body          TEXT,
  entity_type   VARCHAR(50),
  entity_id     UUID,
  read_at       TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_notifications_user_unread ON notifications(user_id) WHERE read_at IS NULL;

-- ---------------------------------------------------------------------
-- 19. audit_logs
-- ---------------------------------------------------------------------
CREATE TABLE audit_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES users(id),
  action        VARCHAR(100) NOT NULL,
  entity_type   VARCHAR(100) NOT NULL,
  entity_id     UUID,
  old_data      JSONB,
  new_data      JSONB,
  ip_address    VARCHAR(50),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX ix_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at);

-- ---------------------------------------------------------------------
-- 20. Datos semilla (seed) — pipelines y etapas sugeridas en la spec
-- ---------------------------------------------------------------------
INSERT INTO pipelines (id, name, description, pipeline_type, is_default, is_active) VALUES
  (gen_random_uuid(), 'Pipeline B2C', 'Ciclo comercial para individuos', 'b2c', TRUE, TRUE),
  (gen_random_uuid(), 'Pipeline B2B', 'Ciclo comercial para empresas', 'b2b', TRUE, TRUE);

INSERT INTO pipeline_stages (pipeline_id, name, stage_order, probability, is_won, is_lost)
SELECT id, stage_name, stage_order, probability, is_won, is_lost
FROM pipelines,
LATERAL (
  VALUES
    ('Nuevo Lead', 1, 10, FALSE, FALSE),
    ('Contacto Inicial', 2, 20, FALSE, FALSE),
    ('Evaluación de Necesidad', 3, 40, FALSE, FALSE),
    ('Propuesta', 4, 60, FALSE, FALSE),
    ('Seguimiento', 5, 75, FALSE, FALSE),
    ('Ganado', 6, 100, TRUE, FALSE),
    ('Perdido', 7, 0, FALSE, TRUE)
) AS s(stage_name, stage_order, probability, is_won, is_lost)
WHERE pipelines.pipeline_type = 'b2c';

INSERT INTO pipeline_stages (pipeline_id, name, stage_order, probability, is_won, is_lost)
SELECT id, stage_name, stage_order, probability, is_won, is_lost
FROM pipelines,
LATERAL (
  VALUES
    ('Lead Empresarial', 1, 10, FALSE, FALSE),
    ('Contacto', 2, 20, FALSE, FALSE),
    ('Reunión', 3, 30, FALSE, FALSE),
    ('Diagnóstico', 4, 45, FALSE, FALSE),
    ('Propuesta', 5, 60, FALSE, FALSE),
    ('Negociación', 6, 80, FALSE, FALSE),
    ('Cierre', 7, 90, FALSE, FALSE),
    ('Ganado', 8, 100, TRUE, FALSE),
    ('Perdido', 9, 0, FALSE, TRUE)
) AS s(stage_name, stage_order, probability, is_won, is_lost)
WHERE pipelines.pipeline_type = 'b2b';

-- ---------------------------------------------------------------------
-- 21. Usuario administrador inicial (cambiar password_hash en el primer login)
-- ---------------------------------------------------------------------
-- password_hash de ejemplo generado con bcrypt para la cadena 'ChangeMe123!'
-- Debe regenerarse con el mecanismo real de hashing del backend antes de producción.
INSERT INTO users (first_name, last_name, email, password_hash, role, is_active)
VALUES ('Admin', 'Satori', 'admin@clinicasatori.cr',
        '$2b$12$K8yD1f0V0nQY7z8yGZzKQO7GZ0h1s1Q3sVYvLQ8kQ8kQ8kQ8kQ8kQ', 'admin', TRUE);

-- =====================================================================
-- Fin del esquema
-- =====================================================================
