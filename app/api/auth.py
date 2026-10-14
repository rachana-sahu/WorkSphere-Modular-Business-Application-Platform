import re
import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    get_current_user,
)
from app.models import User, Workspace, WorkspaceMembership
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RegisterRequest,
    SessionResponse,
    UserResponse,
)
from app.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_csrf_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionResponse:
    user = User(
        email=request.email,
        display_name=request.display_name,
        password_hash=hash_password(request.password),
    )
    workspace = Workspace(
        name=request.workspace_name,
        slug=_workspace_slug(request.workspace_name),
    )
    db.add_all([user, workspace])
    try:
        db.flush()
        db.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner",
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "registration_conflict",
                "message": "An account or workspace with these details already exists.",
            },
        ) from None

    return _issue_session(response, user.id)


@router.post("/login", response_model=SessionResponse)
def login(
    request: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> SessionResponse:
    user = _authenticate_user(request, db)
    return _issue_session(response, user.id)


@router.post("/token", response_model=AccessTokenResponse)
def create_api_access_token(
    request: LoginRequest, db: Session = Depends(get_db)
) -> AccessTokenResponse:
    user = _authenticate_user(request, db)
    return AccessTokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    _current_user: User = Depends(get_current_user),
) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/api",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite="lax",
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
    )


def _issue_session(response: Response, user_id: UUID) -> SessionResponse:
    expires_in = settings.access_token_expire_minutes * 60
    session_token = create_access_token(user_id)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        max_age=expires_in,
        path="/api",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        create_csrf_token(session_token),
        max_age=expires_in,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite="lax",
    )
    return SessionResponse(expires_in=expires_in)


def _authenticate_user(request: LoginRequest, db: Session) -> User:
    user = db.scalar(select(User).where(User.email == request.email))
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(request.password, password_hash)
    if user is None or not user.is_active or not password_matches:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_credentials",
                "message": "Email or password is incorrect.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _workspace_slug(workspace_name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", workspace_name).encode(
        "ascii", "ignore"
    ).decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-")
    return (slug or "workspace")[:80].strip("-")
