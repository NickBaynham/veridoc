"""Knowledge model build pipeline (V1 scaffold; specialized builders per model_type)."""

from app.services.models.model_build_worker import run_build_knowledge_model_version_sync

__all__ = ["run_build_knowledge_model_version_sync"]
