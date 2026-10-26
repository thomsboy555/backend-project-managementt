-- Jalankan di SQL Editor Supabase / Neon.
-- PERINGATAN: baris DROP akan menghapus tabel lama beserta isinya.
DROP TABLE IF EXISTS comments, tasks, project_members, projects, users, departments CASCADE;

CREATE TABLE departments (
    id   SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL
);

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    name          VARCHAR NOT NULL,
    email         VARCHAR NOT NULL UNIQUE
);

CREATE TABLE projects (
    id          SERIAL PRIMARY KEY,
    owner_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title       VARCHAR NOT NULL,
    description TEXT,
    status      VARCHAR DEFAULT 'planning'
);

-- Tabel pivot (many-to-many projects <-> users)
CREATE TABLE project_members (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE tasks (
    id          SERIAL PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title       VARCHAR NOT NULL,
    status      VARCHAR DEFAULT 'todo'
);

CREATE TABLE comments (
    id      SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL
);
