-- PostgreSQL schema for leave/recovery management

CREATE TYPE employee_status AS ENUM ('active', 'inactive');
CREATE TYPE role_code AS ENUM ('EMPLOYEE', 'MANAGER_FUNCTIONAL', 'MANAGER_HIERARCHICAL', 'HR');
CREATE TYPE balance_bucket AS ENUM ('LEAVE', 'RECOVERY');
CREATE TYPE request_unit AS ENUM ('DAY', 'HOUR');
CREATE TYPE request_status AS ENUM (
  'DRAFT',
  'SUBMITTED',
  'PENDING_FUNCTIONAL',
  'PENDING_HIERARCHICAL',
  'PENDING_HR',
  'APPROVED',
  'REJECTED',
  'CANCELLED'
);
CREATE TYPE approval_decision AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
CREATE TYPE notification_channel AS ENUM ('IN_APP', 'EMAIL');
CREATE TYPE transaction_type AS ENUM (
  'ALLOCATION',
  'MANUAL_ADJUSTMENT_PLUS',
  'MANUAL_ADJUSTMENT_MINUS',
  'RESERVE',
  'RELEASE_RESERVE',
  'CONSUME',
  'REVERT_CONSUME'
);
CREATE TYPE transaction_direction AS ENUM ('CREDIT', 'DEBIT');

CREATE TABLE teams (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE employees (
  id BIGSERIAL PRIMARY KEY,
  employee_code VARCHAR(32) NOT NULL UNIQUE,
  first_name VARCHAR(120) NOT NULL,
  last_name VARCHAR(120) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  phone VARCHAR(40),
  job_title VARCHAR(120),
  hire_date DATE NOT NULL,
  status employee_status NOT NULL DEFAULT 'active',
  team_id BIGINT REFERENCES teams(id),
  functional_manager_id BIGINT REFERENCES employees(id),
  hierarchical_manager_id BIGINT REFERENCES employees(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_not_self_functional_manager CHECK (functional_manager_id IS NULL OR functional_manager_id <> id),
  CONSTRAINT chk_not_self_hierarchical_manager CHECK (hierarchical_manager_id IS NULL OR hierarchical_manager_id <> id)
);

CREATE TABLE roles (
  id BIGSERIAL PRIMARY KEY,
  code role_code NOT NULL UNIQUE,
  label VARCHAR(120) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE employee_roles (
  id BIGSERIAL PRIMARY KEY,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (employee_id, role_id)
);

CREATE TABLE leave_types (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(40) NOT NULL UNIQUE,
  label VARCHAR(120) NOT NULL,
  balance_bucket balance_bucket,
  unit request_unit NOT NULL DEFAULT 'DAY',
  requires_attachment BOOLEAN NOT NULL DEFAULT FALSE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE employee_balances (
  id BIGSERIAL PRIMARY KEY,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  bucket balance_bucket NOT NULL,
  acquired_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
  used_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
  reserved_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
  available_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (employee_id, bucket),
  CONSTRAINT chk_non_negative_balance_values CHECK (
    acquired_amount >= 0 AND used_amount >= 0 AND reserved_amount >= 0 AND available_amount >= 0
  )
);

CREATE TABLE leave_requests (
  id BIGSERIAL PRIMARY KEY,
  request_number VARCHAR(40) NOT NULL UNIQUE,
  employee_id BIGINT NOT NULL REFERENCES employees(id),
  leave_type_id BIGINT NOT NULL REFERENCES leave_types(id),
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  requested_quantity NUMERIC(10,2) NOT NULL,
  reason TEXT,
  status request_status NOT NULL DEFAULT 'DRAFT',
  current_approver_id BIGINT REFERENCES employees(id),
  submitted_at TIMESTAMPTZ,
  finalized_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_request_dates CHECK (start_date <= end_date),
  CONSTRAINT chk_requested_quantity_positive CHECK (requested_quantity > 0)
);

CREATE TABLE request_approvals (
  id BIGSERIAL PRIMARY KEY,
  leave_request_id BIGINT NOT NULL REFERENCES leave_requests(id) ON DELETE CASCADE,
  step_order SMALLINT NOT NULL,
  step_role role_code NOT NULL,
  approver_id BIGINT NOT NULL REFERENCES employees(id),
  decision approval_decision NOT NULL DEFAULT 'PENDING',
  comment TEXT,
  decided_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (leave_request_id, step_order),
  CONSTRAINT chk_step_order_range CHECK (step_order BETWEEN 1 AND 3),
  CONSTRAINT chk_reject_comment CHECK (decision <> 'REJECTED' OR comment IS NOT NULL)
);

CREATE TABLE balance_transactions (
  id BIGSERIAL PRIMARY KEY,
  employee_id BIGINT NOT NULL REFERENCES employees(id),
  bucket balance_bucket NOT NULL,
  request_id BIGINT REFERENCES leave_requests(id),
  transaction_type transaction_type NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  direction transaction_direction NOT NULL,
  effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
  note TEXT,
  performed_by BIGINT REFERENCES employees(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_transaction_amount_positive CHECK (amount > 0)
);

CREATE TABLE request_attachments (
  id BIGSERIAL PRIMARY KEY,
  leave_request_id BIGINT NOT NULL REFERENCES leave_requests(id) ON DELETE CASCADE,
  file_name VARCHAR(255) NOT NULL,
  file_path TEXT NOT NULL,
  mime_type VARCHAR(120),
  uploaded_by BIGINT REFERENCES employees(id),
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE notifications (
  id BIGSERIAL PRIMARY KEY,
  employee_id BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  channel notification_channel NOT NULL,
  title VARCHAR(180) NOT NULL,
  message TEXT NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_logs (
  id BIGSERIAL PRIMARY KEY,
  actor_id BIGINT REFERENCES employees(id),
  entity_type VARCHAR(50) NOT NULL,
  entity_id BIGINT NOT NULL,
  action VARCHAR(80) NOT NULL,
  old_value JSONB,
  new_value JSONB,
  ip_address VARCHAR(45),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_employees_team_id ON employees(team_id);
CREATE INDEX idx_leave_requests_employee_status ON leave_requests(employee_id, status);
CREATE INDEX idx_leave_requests_approver_status ON leave_requests(current_approver_id, status);
CREATE INDEX idx_leave_requests_dates ON leave_requests(start_date, end_date);
CREATE INDEX idx_request_approvals_req_step ON request_approvals(leave_request_id, step_order);
CREATE INDEX idx_balance_transactions_emp_bucket_date ON balance_transactions(employee_id, bucket, effective_date);
