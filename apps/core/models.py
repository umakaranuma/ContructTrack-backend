"""
Abstract base model injected into every app model.
tenant_id is the primary isolation mechanism — every query MUST filter by it.
Using an abstract model (not a concrete one) means no extra DB table is created.
"""
import uuid
from django.db import models


class TenantScopedModel(models.Model):
    """
    Every data model that belongs to a tenant inherits this.
    It enforces the multi-tenant pattern: a site, bill, worker, etc.
    can never be accessed without a tenant context.
    """
    # tenant FK is NOT defined here to avoid circular imports between apps.
    # Each app declares it explicitly; this base just provides created_at / updated_at.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # no table created — fields are copied into child models


class UUIDModel(models.Model):
    """
    UUID primary key base.
    Using UUID instead of auto-increment prevents enumeration attacks and
    simplifies multi-region or offline-first data merging.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
