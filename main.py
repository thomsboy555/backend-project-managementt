from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

import models
from models import Comment, Department, Project, ProjectMember, Task, User

app = FastAPI(
    title="Project Management REST API",
    description="REST API manajemen project: departments, users, projects, tasks, comments.",
)

# Buat tabel yang belum ada (tidak mengubah tabel yang sudah ada)
try:
    models.Base.metadata.create_all(bind=models.engine)
except Exception as e:  # jangan sampai app mati total kalau DB sedang bermasalah
    print("Gagal membuat tabel:", e)


# ---------------------------------------------------------------- Helper
def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"{label} tidak ditemukan")
    return obj


def check_fk(db: Session, model, obj_id: Optional[int], label: str):
    """Pastikan foreign key yang dikirim user benar-benar ada (kalau diisi)."""
    if obj_id is not None and db.get(model, obj_id) is None:
        raise HTTPException(status_code=400, detail=f"{label} dengan id {obj_id} tidak ditemukan")


def commit(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Data tidak valid atau melanggar aturan database (contoh: email sudah dipakai)",
        )


def save_new(db: Session, obj):
    db.add(obj)
    commit(db)
    db.refresh(obj)
    return obj


def apply_update(db: Session, obj, data: dict):
    for key, value in data.items():
        setattr(obj, key, value)
    commit(db)
    db.refresh(obj)
    return obj


# ---------------------------------------------------------------- Error handler
# Semua error dikembalikan dengan format {"error": "..."}
@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    details = "; ".join(
        f"{'.'.join(str(x) for x in e['loc'] if x != 'body')}: {e['msg']}" for e in exc.errors()
    )
    return JSONResponse(status_code=400, content={"error": f"Input tidak valid - {details}"})


@app.exception_handler(Exception)
async def server_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"error": "Terjadi kesalahan pada server"})


# ---------------------------------------------------------------- Schema (validasi input)
ProjectStatus = Literal["planning", "ongoing", "done"]
TaskStatus = Literal["todo", "in_progress", "done"]


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1)


class UserCreate(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    department_id: Optional[int] = None


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[str] = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    department_id: Optional[int] = None


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1)
    description: Optional[str] = None
    status: ProjectStatus = "planning"
    owner_id: Optional[int] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    owner_id: Optional[int] = None


class MemberAdd(BaseModel):
    user_id: int


class TaskCreate(BaseModel):
    project_id: int
    title: str = Field(min_length=1)
    status: TaskStatus = "todo"
    assignee_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    status: Optional[TaskStatus] = None
    assignee_id: Optional[int] = None


class CommentCreate(BaseModel):
    task_id: int
    user_id: Optional[int] = None
    content: str = Field(min_length=1)


# ---------------------------------------------------------------- Root
@app.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI Server Running"}


# ---------------------------------------------------------------- Departments
@app.get("/departments", status_code=200)
def get_departments(db: Session = Depends(get_db)):
    data = [to_dict(d) for d in db.query(Department).order_by(Department.id).all()]
    return {"message": "Data berhasil diambil", "data": data}


@app.post("/departments", status_code=201)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    dept = save_new(db, Department(name=payload.name))
    return {"message": "Department berhasil dibuat", "data": to_dict(dept)}


# ---------------------------------------------------------------- Users
@app.get("/users", status_code=200)
def get_users(db: Session = Depends(get_db)):
    data = [to_dict(u) for u in db.query(User).order_by(User.id).all()]
    return {"message": "Data berhasil diambil", "data": data}


@app.get("/users/{user_id}", status_code=200)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id, "User")
    return {"message": "Data ditemukan", "data": to_dict(user)}


@app.post("/users", status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    check_fk(db, Department, payload.department_id, "Department")
    user = save_new(db, User(**payload.model_dump()))
    return {"message": "User berhasil dibuat", "data": to_dict(user)}


@app.put("/users/{user_id}", status_code=200)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id, "User")
    data = payload.model_dump(exclude_unset=True)
    check_fk(db, Department, data.get("department_id"), "Department")
    user = apply_update(db, user, data)
    return {"message": "User berhasil diperbarui", "data": to_dict(user)}


@app.delete("/users/{user_id}", status_code=200)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id, "User")
    db.delete(user)
    commit(db)
    return {"message": "User berhasil dihapus"}


# ---------------------------------------------------------------- Projects (CRUD utama)
@app.get("/projects", status_code=200)
def get_projects(status: Optional[ProjectStatus] = None, db: Session = Depends(get_db)):
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    data = [to_dict(p) for p in query.order_by(Project.id).all()]
    return {"message": "Data berhasil diambil", "data": data}


@app.get("/projects/{project_id}", status_code=200)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, project_id, "Project")
    owner = db.get(User, project.owner_id) if project.owner_id else None
    members = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project_id)
        .all()
    )
    tasks = db.query(Task).filter(Task.project_id == project_id).order_by(Task.id).all()
    data = to_dict(project)
    data["owner"] = to_dict(owner) if owner else None
    data["members"] = [to_dict(m) for m in members]
    data["tasks"] = [to_dict(t) for t in tasks]
    return {"message": "Data ditemukan", "data": data}


@app.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    check_fk(db, User, payload.owner_id, "Owner (user)")
    project = save_new(db, Project(**payload.model_dump()))
    return {"message": "Project berhasil dibuat", "data": to_dict(project)}


@app.put("/projects/{project_id}", status_code=200)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, project_id, "Project")
    data = payload.model_dump(exclude_unset=True)
    check_fk(db, User, data.get("owner_id"), "Owner (user)")
    project = apply_update(db, project, data)
    return {"message": "Project berhasil diperbarui", "data": to_dict(project)}


@app.delete("/projects/{project_id}", status_code=200)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, project_id, "Project")
    db.delete(project)
    commit(db)
    return {"message": "Project berhasil dihapus"}


# ---------------------------------------------------------------- Project members (many-to-many)
@app.get("/projects/{project_id}/members", status_code=200)
def get_members(project_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id, "Project")
    members = (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project_id)
        .all()
    )
    return {"message": "Data berhasil diambil", "data": [to_dict(m) for m in members]}


@app.post("/projects/{project_id}/members", status_code=201)
def add_member(project_id: int, payload: MemberAdd, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id, "Project")
    get_or_404(db, User, payload.user_id, "User")
    exists = db.get(ProjectMember, (project_id, payload.user_id))
    if exists:
        raise HTTPException(status_code=400, detail="User sudah menjadi member project ini")
    save_new(db, ProjectMember(project_id=project_id, user_id=payload.user_id))
    return {
        "message": "Member berhasil ditambahkan",
        "data": {"project_id": project_id, "user_id": payload.user_id},
    }


@app.delete("/projects/{project_id}/members/{user_id}", status_code=200)
def remove_member(project_id: int, user_id: int, db: Session = Depends(get_db)):
    member = db.get(ProjectMember, (project_id, user_id))
    if not member:
        raise HTTPException(status_code=404, detail="Member tidak ditemukan di project ini")
    db.delete(member)
    commit(db)
    return {"message": "Member berhasil dihapus dari project"}


# ---------------------------------------------------------------- Tasks
@app.get("/tasks", status_code=200)
def get_tasks(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Task)
    if project_id is not None:
        query = query.filter(Task.project_id == project_id)
    data = [to_dict(t) for t in query.order_by(Task.id).all()]
    return {"message": "Data berhasil diambil", "data": data}


@app.get("/tasks/{task_id}", status_code=200)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = get_or_404(db, Task, task_id, "Task")
    return {"message": "Data ditemukan", "data": to_dict(task)}


@app.post("/tasks", status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    check_fk(db, Project, payload.project_id, "Project")
    check_fk(db, User, payload.assignee_id, "Assignee (user)")
    task = save_new(db, Task(**payload.model_dump()))
    return {"message": "Task berhasil dibuat", "data": to_dict(task)}


@app.put("/tasks/{task_id}", status_code=200)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = get_or_404(db, Task, task_id, "Task")
    data = payload.model_dump(exclude_unset=True)
    check_fk(db, User, data.get("assignee_id"), "Assignee (user)")
    task = apply_update(db, task, data)
    return {"message": "Task berhasil diperbarui", "data": to_dict(task)}


@app.delete("/tasks/{task_id}", status_code=200)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = get_or_404(db, Task, task_id, "Task")
    db.delete(task)
    commit(db)
    return {"message": "Task berhasil dihapus"}


# ---------------------------------------------------------------- Comments
@app.get("/tasks/{task_id}/comments", status_code=200)
def get_comments(task_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Task, task_id, "Task")
    comments = db.query(Comment).filter(Comment.task_id == task_id).order_by(Comment.id).all()
    return {"message": "Data berhasil diambil", "data": [to_dict(c) for c in comments]}


@app.post("/comments", status_code=201)
def create_comment(payload: CommentCreate, db: Session = Depends(get_db)):
    check_fk(db, Task, payload.task_id, "Task")
    check_fk(db, User, payload.user_id, "User")
    comment = save_new(db, Comment(**payload.model_dump()))
    return {"message": "Komentar berhasil ditambahkan", "data": to_dict(comment)}


@app.delete("/comments/{comment_id}", status_code=200)
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    comment = get_or_404(db, Comment, comment_id, "Komentar")
    db.delete(comment)
    commit(db)
    return {"message": "Komentar berhasil dihapus"}
