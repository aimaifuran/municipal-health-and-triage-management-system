"""Abstract base models shared across the application."""
from __future__ import annotations

import uuid

from django.db import models


class UUIDTimestampedModel(models.Model):
    """Base model with UUID primary key and audit timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def active(self) -> SoftDeleteQuerySet:
        return self.filter(archived_at__isnull=True)

    def archived(self) -> SoftDeleteQuerySet:
        return self.filter(archived_at__isnull=False)


class SoftDeleteManager(models.Manager):
    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def all_with_archived(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(UUIDTimestampedModel):
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def archive(self) -> None:
        from django.utils import timezone

        self.archived_at = timezone.now()
        self.save(update_fields=["archived_at", "updated_at"])

    def restore(self) -> None:
        self.archived_at = None
        self.save(update_fields=["archived_at", "updated_at"])

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None
