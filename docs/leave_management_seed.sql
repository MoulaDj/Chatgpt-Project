-- Minimal seed data for leave/recovery management demo

INSERT INTO teams (name, description) VALUES
('RH', 'Ressources Humaines'),
('IT', 'Equipe informatique'),
('Finance', 'Equipe finance');

INSERT INTO roles (code, label) VALUES
('EMPLOYEE', 'Employe'),
('MANAGER_FUNCTIONAL', 'Manager fonctionnel'),
('MANAGER_HIERARCHICAL', 'Manager hierarchique'),
('HR', 'Ressources Humaines');

INSERT INTO employees (employee_code, first_name, last_name, email, job_title, hire_date, team_id)
VALUES
('E1001', 'Sami', 'Rahmani', 'sami.rahmani@company.com', 'HR Officer', '2022-01-10', (SELECT id FROM teams WHERE name='RH')),
('E1002', 'Nadia', 'Benali', 'nadia.benali@company.com', 'Delivery Manager', '2021-06-14', (SELECT id FROM teams WHERE name='IT')),
('E1003', 'Karim', 'Haddad', 'karim.haddad@company.com', 'Engineering Manager', '2020-02-01', (SELECT id FROM teams WHERE name='IT')),
('E1004', 'Yassine', 'Mansouri', 'yassine.mansouri@company.com', 'Software Engineer', '2024-03-11', (SELECT id FROM teams WHERE name='IT')),
('E1005', 'Lina', 'Alaoui', 'lina.alaoui@company.com', 'Accountant', '2023-09-04', (SELECT id FROM teams WHERE name='Finance'));

-- manager links
UPDATE employees e
SET functional_manager_id = (SELECT id FROM employees WHERE employee_code = 'E1002'),
    hierarchical_manager_id = (SELECT id FROM employees WHERE employee_code = 'E1003')
WHERE e.employee_code IN ('E1004', 'E1005');

-- roles
INSERT INTO employee_roles (employee_id, role_id)
SELECT e.id, r.id
FROM employees e
JOIN roles r ON r.code = 'HR'
WHERE e.employee_code = 'E1001';

INSERT INTO employee_roles (employee_id, role_id)
SELECT e.id, r.id
FROM employees e
JOIN roles r ON r.code = 'MANAGER_FUNCTIONAL'
WHERE e.employee_code = 'E1002';

INSERT INTO employee_roles (employee_id, role_id)
SELECT e.id, r.id
FROM employees e
JOIN roles r ON r.code = 'MANAGER_HIERARCHICAL'
WHERE e.employee_code = 'E1003';

INSERT INTO employee_roles (employee_id, role_id)
SELECT e.id, r.id
FROM employees e
JOIN roles r ON r.code = 'EMPLOYEE'
WHERE e.employee_code IN ('E1004', 'E1005');

-- leave types
INSERT INTO leave_types (code, label, balance_bucket, unit, requires_attachment) VALUES
('ANNUAL_LEAVE', 'Conge annuel', 'LEAVE', 'DAY', FALSE),
('RECOVERY_DAY', 'Jour de recuperation', 'RECOVERY', 'DAY', FALSE),
('AUTHORIZATION', 'Demande autorisation', NULL, 'HOUR', FALSE);

-- balances for end users
INSERT INTO employee_balances (employee_id, bucket, acquired_amount, used_amount, reserved_amount, available_amount)
SELECT e.id, b.bucket, b.acquired, 0, 0, b.acquired
FROM employees e
CROSS JOIN (
  VALUES
    ('LEAVE'::balance_bucket, 24.00::numeric),
    ('RECOVERY'::balance_bucket, 8.00::numeric)
) AS b(bucket, acquired)
WHERE e.employee_code IN ('E1004', 'E1005');

-- sample request in progress for E1004
INSERT INTO leave_requests (
  request_number, employee_id, leave_type_id, start_date, end_date,
  requested_quantity, reason, status, current_approver_id, submitted_at
)
VALUES (
  'REQ-2026-0001',
  (SELECT id FROM employees WHERE employee_code='E1004'),
  (SELECT id FROM leave_types WHERE code='ANNUAL_LEAVE'),
  '2026-06-08',
  '2026-06-10',
  3,
  'Conge familial',
  'PENDING_FUNCTIONAL',
  (SELECT id FROM employees WHERE employee_code='E1002'),
  NOW()
);

-- reserve balance for pending request
INSERT INTO balance_transactions (employee_id, bucket, request_id, transaction_type, amount, direction, note, performed_by)
VALUES (
  (SELECT id FROM employees WHERE employee_code='E1004'),
  'LEAVE',
  (SELECT id FROM leave_requests WHERE request_number='REQ-2026-0001'),
  'RESERVE',
  3,
  'DEBIT',
  'Reservation automatique a la soumission',
  (SELECT id FROM employees WHERE employee_code='E1004')
);

UPDATE employee_balances
SET reserved_amount = reserved_amount + 3,
    available_amount = available_amount - 3,
    updated_at = NOW()
WHERE employee_id = (SELECT id FROM employees WHERE employee_code='E1004')
  AND bucket = 'LEAVE';

INSERT INTO request_approvals (leave_request_id, step_order, step_role, approver_id, decision)
VALUES
((SELECT id FROM leave_requests WHERE request_number='REQ-2026-0001'), 1, 'MANAGER_FUNCTIONAL', (SELECT id FROM employees WHERE employee_code='E1002'), 'PENDING'),
((SELECT id FROM leave_requests WHERE request_number='REQ-2026-0001'), 2, 'MANAGER_HIERARCHICAL', (SELECT id FROM employees WHERE employee_code='E1003'), 'PENDING'),
((SELECT id FROM leave_requests WHERE request_number='REQ-2026-0001'), 3, 'HR', (SELECT id FROM employees WHERE employee_code='E1001'), 'PENDING');
