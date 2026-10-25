from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import models

app = FastAPI(title="Project Management REST API")

def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "planning"

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

@app.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI Server Running"}

@app.get("/projects", status_code=status.HTTP_200_OK)
def get_all_projects(db: Session = Depends(get_db)):
    projects = db.query(models.Project).all()
    return {"message": "Data berhasil diambil", "data": projects}

@app.get("/projects/{project_id}", status_code=status.HTTP_200_OK)
def get_project_by_id(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project tidak ditemukan")
    return {"message": "Data ditemukan", "data": project}

@app.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    new_project = models.Project(
        title=payload.title,
        description=payload.description,
        status=payload.status
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return {"message": "Project berhasil dibuat", "data": new_project}

@app.put("/projects/{project_id}", status_code=status.HTTP_200_OK)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project_query = db.query(models.Project).filter(models.Project.id == project_id)
    if not project_query.first():
        raise HTTPException(status_code=404, detail="Project tidak ditemukan")

    update_data = payload.dict(exclude_unset=True)
    project_query.update(update_data, synchronize_session=False)
    db.commit()
    return {"message": "Project berhasil diperbarui", "data": project_query.first()}

@app.delete("/projects/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project tidak ditemukan")

    db.delete(project)
    db.commit()
    return {"message": "Project berhasil dihapus"}
