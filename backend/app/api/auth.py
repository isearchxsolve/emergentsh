from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import timedelta

from backend.app.core.database import get_db
from backend.app.core.auth import (
    authenticate_user, create_access_token, get_current_active_user, get_owner_user, get_password_hash, verify_password
)
from backend.app.models import Artifact, CreditTransaction, ManagedArtifact, Message, PipelineEvent, PipelineJob, Project, TokenRevocation, User
from backend.app.schemas import (
    UserCreate, UserUpdate, UserResponse, Token, TokenData, PasswordChange, ManagedUserCreate, ManagedUserUpdate,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is closed. Contact the service owner for credentials.")
    # Kept below solely to make the former behavior explicit in source history.
    result = await db.execute(
        select(User).where((User.username == user_data.username) | (User.email == user_data.email))
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )
    
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=60 * 24 * 7)  # 7 days
    access_token = create_access_token(
        data={"sub": str(user.id), "ver": user.auth_version},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    return current_user


@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    db.add(TokenRevocation(token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest()))
    await db.flush()
    return {"message": "Successfully logged out"}


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.is_superuser and "email" in user_data.model_dump(exclude_unset=True):
        raise HTTPException(400, detail="Change OWNER_EMAIL only through controlled deployment configuration.")
    for field, value in user_data.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.post("/me/password")
async def change_password(
    body: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(body.new_password)
    current_user.auth_version += 1
    await db.flush()
    return {"message": "Password updated; sign in again on all devices."}


@router.get("/admin/users", response_model=list[UserResponse])
async def admin_list_users(db: AsyncSession = Depends(get_db), _: User = Depends(get_owner_user)):
    return (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()


@router.get("/admin/history")
async def admin_customer_history(db: AsyncSession = Depends(get_db), _: User = Depends(get_owner_user)):
    """Owner-only full customer lineage without exposing any binary payload."""
    users = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    projects = (await db.execute(select(Project).order_by(Project.created_at.desc()))).scalars().all()
    artifacts = (await db.execute(select(Artifact).order_by(Artifact.created_at.desc()))).scalars().all()
    jobs = (await db.execute(select(PipelineJob).order_by(PipelineJob.created_at.desc()))).scalars().all()
    archives = (await db.execute(select(ManagedArtifact))).scalars().all()
    credits = (await db.execute(select(CreditTransaction).order_by(CreditTransaction.created_at.desc()))).scalars().all()
    messages = (await db.execute(select(Message).order_by(Message.created_at.desc()))).scalars().all()
    events = (await db.execute(select(PipelineEvent).order_by(PipelineEvent.created_at.desc()))).scalars().all()
    project_owner = {project.id: project.owner_id for project in projects}
    by_owner = {user.id: {"user": {"id": user.id, "email": user.email, "username": user.username, "full_name": user.full_name, "is_active": user.is_active, "credits": user.credits, "created_at": user.created_at, "updated_at": user.updated_at, "last_login": user.last_login}, "projects": [], "artifacts": [], "jobs": [], "deliveries": [], "credit_activity": [], "message_activity": [], "pipeline_activity": []} for user in users}
    for project in projects:
        by_owner[project.owner_id]["projects"].append({"id": project.id, "name": project.name, "status": project.status, "preview_url": project.preview_url, "created_at": project.created_at})
    for artifact in artifacts:
        owner_id = project_owner.get(artifact.project_id)
        if owner_id in by_owner:
            by_owner[owner_id]["artifacts"].append({"id": artifact.id, "project_id": artifact.project_id, "name": artifact.name, "path": artifact.path, "content_type": artifact.content_type, "size": artifact.size, "created_at": artifact.created_at})
    for job in jobs:
        if job.user_id in by_owner:
            by_owner[job.user_id]["jobs"].append({"job_id": job.job_id, "status": job.status, "target": job.target, "prompt": job.prompt, "artifacts": job.artifacts, "preview_url": job.preview_url, "created_at": job.created_at})
    for archive in archives:
        if archive.user_id in by_owner:
            by_owner[archive.user_id]["deliveries"].append({"id": archive.id, "job_id": archive.pipeline_job_id, "name": archive.name, "content_type": archive.content_type, "byte_size": archive.byte_size, "sha256": archive.sha256, "created_at": archive.created_at})
    for credit in credits:
        if credit.user_id in by_owner:
            by_owner[credit.user_id]["credit_activity"].append({"id": credit.id, "amount": credit.amount, "type": credit.transaction_type, "description": credit.description, "project_id": credit.project_id, "created_at": credit.created_at})
    for message in messages:
        if message.user_id in by_owner:
            by_owner[message.user_id]["message_activity"].append({"id": message.id, "project_id": message.project_id, "role": message.role, "content": message.content, "agent_role": message.agent_role, "created_at": message.created_at})
    job_owner = {job.job_id: job.user_id for job in jobs}
    for event in events:
        owner_id = job_owner.get(event.job_id)
        if owner_id in by_owner:
            by_owner[owner_id]["pipeline_activity"].append({"id": event.id, "job_id": event.job_id, "type": event.event_type, "role": event.role, "data": event.data, "created_at": event.created_at})
    return {"customers": list(by_owner.values())}


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_user(body: ManagedUserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_owner_user)):
    exists = await db.execute(select(User.id).where((func.lower(User.email) == body.email.lower()) | (User.username == body.username)))
    if exists.scalar_one_or_none():
        raise HTTPException(409, "Username or email already exists")
    user = User(email=body.email, username=body.username, full_name=body.full_name, hashed_password=get_password_hash(body.password), credits=body.credits, is_superuser=False)
    db.add(user)
    await db.flush(); await db.refresh(user)
    return user


@router.patch("/admin/users/{user_id}", response_model=UserResponse)
async def admin_update_user(user_id: str, body: ManagedUserUpdate, db: AsyncSession = Depends(get_db), owner: User = Depends(get_owner_user)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == owner.id and (body.is_active is False or body.email is not None or body.username is not None):
        raise HTTPException(400, "The owner identity cannot be disabled or renamed")
    changes = body.model_dump(exclude_unset=True)
    if "email" in changes:
        duplicate = await db.execute(select(User.id).where(func.lower(User.email) == changes["email"].lower(), User.id != user.id))
        if duplicate.scalar_one_or_none():
            raise HTTPException(409, "Email already exists")
    if "username" in changes:
        duplicate = await db.execute(select(User.id).where(User.username == changes["username"], User.id != user.id))
        if duplicate.scalar_one_or_none():
            raise HTTPException(409, "Username already exists")
    if "password" in changes:
        user.hashed_password = get_password_hash(changes.pop("password")); user.auth_version += 1
    if changes.get("is_active") is False:
        user.auth_version += 1
    for field, value in changes.items(): setattr(user, field, value)
    await db.flush(); await db.refresh(user)
    return user
