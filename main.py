import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

# Database
from database import db, create_document, get_documents

app = FastAPI(title="SaaS Starter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Utils ----------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    d = {**doc}
    _id = d.pop("_id", None)
    if _id is not None:
        d["id"] = str(_id)
    # Convert datetimes to isoformat if present
    for k, v in list(d.items()):
        try:
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        except Exception:
            pass
    return d


# ---------- Models ----------
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    status: str = Field("active", description="active | paused | completed")
    owner_email: Optional[str] = Field(None, description="Owner email")
    due_date: Optional[str] = Field(None, description="ISO date (optional)")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None)
    owner_email: Optional[str] = Field(None)
    due_date: Optional[str] = Field(None)


class ProjectOut(ProjectCreate):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------- Routes ----------
@app.get("/")
def read_root():
    return {"message": "SaaS Starter Backend is running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Projects CRUD
COLL = "project"


@app.get("/api/projects", response_model=List[ProjectOut])
def list_projects(limit: int = 100):
    docs = get_documents(COLL, {}, limit)
    return [ProjectOut(**serialize_doc(d)) for d in docs]


@app.post("/api/projects", response_model=ProjectOut)
def create_project(payload: ProjectCreate):
    new_id = create_document(COLL, payload)
    doc = db[COLL].find_one({"_id": ObjectId(new_id)})
    return ProjectOut(**serialize_doc(doc))


@app.put("/api/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectUpdate):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project id")
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")
    changes["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    res = db[COLL].find_one_and_update(
        {"_id": ObjectId(project_id)},
        {"$set": changes},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectOut(**serialize_doc(res))


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project id")
    res = db[COLL].delete_one({"_id": ObjectId(project_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
