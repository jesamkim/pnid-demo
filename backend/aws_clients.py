"""AWS client factory.

All AWS calls MUST go through these factories so credential profile and region
are uniform across the project.
"""
from __future__ import annotations

import os
from functools import lru_cache

import boto3
from botocore.config import Config

from backend.config import get_settings


@lru_cache(maxsize=1)
def get_session() -> boto3.Session:
    """Build a boto3 session.

    Order of precedence for credentials:
      1. `AWS_PROFILE_OVERRIDE` env var (explicit override)
      2. `AWS_EXECUTION_ENV` set by ECS/Lambda → use the task role
         (no profile, default credential chain)
      3. settings.aws_profile from config/settings.yaml (local dev)

    The ECS branch is critical: in production we run as a Fargate task
    whose IAM role provides credentials via the ECS metadata endpoint.
    Forcing `profile_name="profile2"` there fails with ProfileNotFound.
    """
    settings = get_settings()
    region = settings.aws_region
    override = os.environ.get("AWS_PROFILE_OVERRIDE")
    if override:
        return boto3.Session(profile_name=override, region_name=region)
    if os.environ.get("AWS_EXECUTION_ENV") or os.environ.get(
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"
    ):
        return boto3.Session(region_name=region)
    return boto3.Session(profile_name=settings.aws_profile, region_name=region)


@lru_cache(maxsize=1)
def get_bedrock_runtime():
    cfg = Config(read_timeout=300, connect_timeout=60, retries={"max_attempts": 3})
    return get_session().client("bedrock-runtime", config=cfg)


@lru_cache(maxsize=1)
def get_bedrock():
    return get_session().client("bedrock")


@lru_cache(maxsize=1)
def get_s3():
    return get_session().client("s3")
