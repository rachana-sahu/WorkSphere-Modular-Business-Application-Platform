from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_workspace_roles
from app.models import Channel, ChannelMessage, User
from app.schemas.communication import (
    ChannelCreate,
    ChannelResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/communication",
    tags=["Communication"],
    dependencies=[Depends(require_workspace_roles("owner", "admin", "member"))],
)


@router.get("/channels", response_model=list[ChannelResponse])
def list_channels(workspace_id: UUID, db: Session = Depends(get_db)) -> list[Channel]:
    return list(
        db.scalars(
            select(Channel)
            .where(Channel.workspace_id == workspace_id)
            .order_by(Channel.name, Channel.id)
        ).all()
    )


@router.post(
    "/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_channel(
    workspace_id: UUID,
    request: ChannelCreate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Channel:
    channel = Channel(
        workspace_id=workspace_id,
        created_by=actor.id,
        name=request.name,
        description=request.description,
    )
    db.add(channel)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "channel_exists",
                "message": "A channel with this name already exists.",
            },
        ) from exc
    return channel


@router.get(
    "/channels/{channel_id}/messages",
    response_model=list[MessageResponse],
)
def list_messages(
    workspace_id: UUID,
    channel_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ChannelMessage]:
    _get_channel(db, workspace_id, channel_id)
    rows = db.scalars(
        select(ChannelMessage)
        .where(
            ChannelMessage.workspace_id == workspace_id,
            ChannelMessage.channel_id == channel_id,
        )
        .order_by(ChannelMessage.created_at.desc(), ChannelMessage.id.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


@router.post(
    "/channels/{channel_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    workspace_id: UUID,
    channel_id: UUID,
    request: MessageCreate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChannelMessage:
    channel = _get_channel(db, workspace_id, channel_id)
    message = ChannelMessage(
        workspace_id=workspace_id,
        channel_id=channel.id,
        author_id=actor.id,
        body=request.body,
    )
    db.add(message)
    db.commit()
    return message


def _get_channel(db: Session, workspace_id: UUID, channel_id: UUID) -> Channel:
    channel = db.scalar(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.workspace_id == workspace_id,
        )
    )
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "channel_not_found", "message": "The channel was not found."},
        )
    return channel
