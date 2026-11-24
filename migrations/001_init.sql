CREATE TABLE users (
  id {{PK}},
  username TEXT NOT NULL,
  username_lower TEXT NOT NULL UNIQUE,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  phone TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student','teacher','admin')),
  is_blocked INTEGER NOT NULL DEFAULT 0,
  teacher_perms TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_login_at TEXT
);
CREATE INDEX idx_users_role ON users(role);

CREATE TABLE user_sessions (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ip TEXT,
  user_agent TEXT,
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_sessions_user ON user_sessions(user_id);

CREATE TABLE grades (
  id {{PK}},
  name TEXT NOT NULL UNIQUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE subjects (
  id {{PK}},
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE test_collections (
  id {{PK}},
  title TEXT NOT NULL,
  subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
  grade_id INTEGER REFERENCES grades(id) ON DELETE SET NULL,
  description TEXT NOT NULL DEFAULT '',
  questions_per_attempt INTEGER NOT NULL DEFAULT 20,
  time_limit_minutes INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 0,
  randomize_questions INTEGER NOT NULL DEFAULT 1,
  randomize_options INTEGER NOT NULL DEFAULT 1,
  show_correct INTEGER NOT NULL DEFAULT 1,
  show_explanation INTEGER NOT NULL DEFAULT 1,
  show_results INTEGER NOT NULL DEFAULT 1,
  is_enabled INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
  publish_at TEXT,
  expires_at TEXT,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_tests_subject ON test_collections(subject_id);
CREATE INDEX idx_tests_status ON test_collections(status, is_enabled);

CREATE TABLE uploaded_documents (
  id {{PK}},
  test_id INTEGER REFERENCES test_collections(id) ON DELETE SET NULL,
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  page_count INTEGER NOT NULL DEFAULT 0,
  method TEXT NOT NULL DEFAULT 'text',
  status TEXT NOT NULL DEFAULT 'processed',
  questions_found INTEGER NOT NULL DEFAULT 0,
  warnings TEXT NOT NULL DEFAULT '[]',
  data {{BLOB}} NOT NULL,
  uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE questions (
  id {{PK}},
  test_id INTEGER NOT NULL REFERENCES test_collections(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  explanation TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','archived')),
  needs_review INTEGER NOT NULL DEFAULT 0,
  confidence REAL NOT NULL DEFAULT 1,
  warnings TEXT NOT NULL DEFAULT '[]',
  document_id INTEGER REFERENCES uploaded_documents(id) ON DELETE SET NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_questions_test ON questions(test_id, status);
CREATE INDEX idx_questions_hash ON questions(test_id, content_hash);

CREATE TABLE answer_options (
  id {{PK}},
  question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  is_correct INTEGER NOT NULL DEFAULT 0,
  position INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_options_question ON answer_options(question_id);

CREATE TABLE quiz_attempts (
  id {{PK}},
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  test_id INTEGER NOT NULL REFERENCES test_collections(id) ON DELETE CASCADE,
  attempt_no INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','completed','expired')),
  question_ids TEXT NOT NULL DEFAULT '[]',
  total_questions INTEGER NOT NULL DEFAULT 0,
  correct_count INTEGER NOT NULL DEFAULT 0,
  incorrect_count INTEGER NOT NULL DEFAULT 0,
  percentage REAL NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL,
  deadline_at TEXT,
  completed_at TEXT,
  time_spent_seconds INTEGER NOT NULL DEFAULT 0,
  UNIQUE (user_id, test_id, attempt_no)
);
CREATE INDEX idx_attempts_user ON quiz_attempts(user_id, status);
CREATE INDEX idx_attempts_test ON quiz_attempts(test_id, status);

CREATE TABLE attempt_questions (
  id {{PK}},
  attempt_id INTEGER NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
  question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
  position INTEGER NOT NULL,
  option_order TEXT NOT NULL,
  UNIQUE (attempt_id, question_id),
  UNIQUE (attempt_id, position)
);

CREATE TABLE student_answers (
  id {{PK}},
  attempt_id INTEGER NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
  question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
  option_id INTEGER REFERENCES answer_options(id) ON DELETE SET NULL,
  is_correct INTEGER NOT NULL DEFAULT 0,
  answered_at TEXT NOT NULL,
  UNIQUE (attempt_id, question_id)
);
CREATE INDEX idx_answers_question ON student_answers(question_id);

CREATE TABLE question_exposure (
  id {{PK}},
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  test_id INTEGER NOT NULL REFERENCES test_collections(id) ON DELETE CASCADE,
  question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  cycle INTEGER NOT NULL DEFAULT 1,
  attempt_id INTEGER REFERENCES quiz_attempts(id) ON DELETE SET NULL,
  served_at TEXT NOT NULL,
  UNIQUE (user_id, test_id, question_id, cycle)
);
CREATE INDEX idx_exposure_user_test ON question_exposure(user_id, test_id);

CREATE TABLE notifications (
  id {{PK}},
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  level TEXT NOT NULL DEFAULT 'info',
  is_announcement INTEGER NOT NULL DEFAULT 0,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_notif_user ON notifications(user_id);

CREATE TABLE notification_reads (
  notification_id INTEGER NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  read_at TEXT NOT NULL,
  PRIMARY KEY (notification_id, user_id)
);

CREATE TABLE audit_logs (
  id {{PK}},
  actor_id INTEGER,
  actor_username TEXT,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  metadata TEXT NOT NULL DEFAULT '{}',
  ip TEXT,
  user_agent TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_actor ON audit_logs(actor_id);

CREATE TABLE login_history (
  id {{PK}},
  user_id INTEGER,
  username TEXT NOT NULL,
  success INTEGER NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  session_id TEXT,
  ip TEXT,
  user_agent TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_login_created ON login_history(created_at);

CREATE TABLE rate_limits (
  id {{PK}},
  k TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_rate_k ON rate_limits(k, created_at);

CREATE TABLE password_resets (
  id {{PK}},
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_by INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE backups (
  id {{PK}},
  kind TEXT NOT NULL DEFAULT 'scheduled',
  status TEXT NOT NULL DEFAULT 'running',
  size_bytes INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT,
  row_counts TEXT NOT NULL DEFAULT '{}',
  verified INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  data {{BLOB}},
  created_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE TABLE settings (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
