import asyncio
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Post, User, create_db_and_tables, get_async_session
from app.images import imagekit
from app.schemas import UserCreate, UserRead, UserUpdate
from app.users import auth_backend, current_active_user, fastapi_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


def upload_to_imagekit(file_object, file_name):
    """Copy and upload a file without blocking FastAPI's event loop."""
    temp_file_path = None

    try:
        suffix = os.path.splitext(file_name)[1]

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file_object, temp_file)

        with open(temp_file_path, "rb") as image_file:
            return imagekit.upload_file(
                file=image_file,
                file_name=file_name,
                options=UploadFileRequestOptions(
                    use_unique_file_name=True,
                    tags=["backend-upload"],
                ),
            )
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


app = FastAPI(lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserUpdate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    caption: str = Form(""),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    file_name = file.filename or "upload"

    try:
        upload_result = await asyncio.to_thread(
            upload_to_imagekit,
            file.file,
            file_name,
        )

        status_code = upload_result.response_metadata.http_status_code

        if status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="The file could not be uploaded",
            )

        content_type = file.content_type or ""
        file_type = "video" if content_type.startswith("video/") else "image"

        post = Post(
            user_id=user.id,
            caption=caption,
            url=upload_result.url,
            file_type=file_type,
            file_name=upload_result.name,
        )

        session.add(post)
        await session.commit()
        await session.refresh(post)

        return post
    finally:
        await file.close()


@app.get("/feed")
async def get_feed(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Post).order_by(Post.created_at.desc()),
    )
    posts = list(result.scalars().all())

    user_result = await session.execute(select(User))
    users = list(user_result.scalars().all())
    user_dict = {stored_user.id: stored_user.email for stored_user in users}

    posts_data = []

    for post in posts:
        posts_data.append(
            {
                "id": str(post.id),
                "user_id": str(post.user_id),
                "caption": post.caption,
                "url": post.url,
                "file_type": post.file_type,
                "file_name": post.file_name,
                "created_at": post.created_at.isoformat(),
                "is_owner": post.user_id == user.id,
                "email": user_dict.get(post.user_id, "Unknown"),
            }
        )

    return {"posts": posts_data}


@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid post ID",
        ) from error

    result = await session.execute(
        select(Post).where(Post.id == post_uuid),
    )
    post = result.scalars().first()

    if post is None:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    if post.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete this post",
        )

    await session.delete(post)
    await session.commit()

    return {
        "success": True,
        "message": "Post deleted successfully",
    }