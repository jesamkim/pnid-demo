"""Showcase stack — static touch-tablet hook demo.

The showcase (under `showcase/`) is a pure static SPA: it never talks to
a backend at runtime, so it needs no VPC, ALB, ECS, or Cognito. The
simplest secure hosting is:

    CloudFront (OAC) ──► private S3 bucket (no public access)

No ALB means there is structurally no `0.0.0.0/0` ingress to worry about
(which security scanners flag), and no Fargate means no idle compute cost.

Deploy:
    cd showcase && npm ci && npm run build      # produces showcase/dist
    cd ../infra/cdk && AWS_PROFILE=profile2 \
        npx cdk deploy PnidShowcase

The CloudFront distribution domain is printed as a stack output.
"""
from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
)
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[3]
DIST_DIR = REPO_ROOT / "showcase" / "dist"


class ShowcaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Private origin bucket — no public access, encrypted, SSL-only.
        bucket = s3.Bucket(
            self,
            "ShowcaseBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )

        # SPA: route 403/404 back to index.html so deep links work.
        distribution = cloudfront.Distribution(
            self,
            "ShowcaseDistribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                ),
            ],
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            comment="P&ID showcase (replay-only kiosk demo)",
        )

        # Upload the built SPA and invalidate the cache on each deploy.
        if DIST_DIR.exists():
            s3deploy.BucketDeployment(
                self,
                "ShowcaseDeploy",
                sources=[s3deploy.Source.asset(str(DIST_DIR))],
                destination_bucket=bucket,
                distribution=distribution,
                distribution_paths=["/*"],
            )

        cdk.CfnOutput(
            self,
            "ShowcaseUrl",
            value=f"https://{distribution.distribution_domain_name}",
            description="CloudFront URL for the P&ID showcase kiosk demo",
        )
        cdk.CfnOutput(
            self,
            "ShowcaseBucketName",
            value=bucket.bucket_name,
            description="Origin S3 bucket for the showcase",
        )
