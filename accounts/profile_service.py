"""Profile updates for authenticated staff."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest

from accounts.profile_storage import delete_profile_picture, upload_profile_picture
from auditlogs.models import AuditAction
from auditlogs.services import AuditService

User = get_user_model()


class ProfileService:
    @staticmethod
    def update_details(
        *,
        user: User,
        validated_data: dict[str, Any],
        request: HttpRequest | None = None,
    ) -> User:
        with transaction.atomic():
            for field in ("first_name", "last_name", "email"):
                setattr(user, field, validated_data[field])
            user.save(update_fields=["first_name", "last_name", "email", "updated_at"])
            AuditService.log(
                action=AuditAction.UPDATE,
                object_type="User",
                object_id=str(user.pk),
                user=user,
                request=request,
                details={"section": "profile_details"},
            )
        return user

    @staticmethod
    def update_picture(
        *,
        user: User,
        uploaded_file,
        request: HttpRequest | None = None,
    ) -> User:
        result = upload_profile_picture(uploaded_file, user_id=str(user.pk))
        new_public_id = result.get("public_id", "")
        new_url = result.get("secure_url") or result.get("url", "")

        with transaction.atomic():
            old_public_id = user.profile_picture_public_id
            user.profile_picture_url = new_url
            user.profile_picture_public_id = new_public_id
            user.save(
                update_fields=[
                    "profile_picture_url",
                    "profile_picture_public_id",
                    "updated_at",
                ]
            )
            AuditService.log(
                action=AuditAction.UPDATE,
                object_type="User",
                object_id=str(user.pk),
                user=user,
                request=request,
                details={"section": "profile_picture"},
            )

        if old_public_id and old_public_id != new_public_id:
            delete_profile_picture(old_public_id)
        return user

    @staticmethod
    def remove_picture(
        *,
        user: User,
        request: HttpRequest | None = None,
    ) -> User:
        old_public_id = user.profile_picture_public_id
        with transaction.atomic():
            user.profile_picture_url = ""
            user.profile_picture_public_id = ""
            user.save(
                update_fields=[
                    "profile_picture_url",
                    "profile_picture_public_id",
                    "updated_at",
                ]
            )
            AuditService.log(
                action=AuditAction.UPDATE,
                object_type="User",
                object_id=str(user.pk),
                user=user,
                request=request,
                details={"section": "profile_picture_removed"},
            )
        if old_public_id:
            delete_profile_picture(old_public_id)
        return user
