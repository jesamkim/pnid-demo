#!/usr/bin/env bash
# Emergency rollback to the pre-BDA stable state (task def :22, image
# pnid-demo:v27@sha256:3d418bd3...). Safe to run repeatedly. Total
# recovery: ECS rolling deploy ~2 min + CloudFront invalidation ~1-2 min.
set -euo pipefail

CLUSTER="PnidDemoApp-ClusterEB0386A7-q8DSY6mrImIm"
SERVICE="PnidDemoApp-ServiceD69D759B-CL8OlUL4bf4N"
STABLE_TD="PnidDemoAppTaskDefA9614226:22"
CF_DIST="E1SRSKOUV081XL"

: "${AWS_PROFILE:=profile2}"
export AWS_PROFILE

echo ">>> Rolling ECS back to ${STABLE_TD} (Textract OCR, v27)"
aws ecs update-service \
  --cluster "${CLUSTER}" \
  --service "${SERVICE}" \
  --task-definition "${STABLE_TD}" \
  --force-new-deployment \
  --query 'service.taskDefinition' \
  --output text

echo ">>> Waiting for service to stabilise"
aws ecs wait services-stable --cluster "${CLUSTER}" --services "${SERVICE}"
echo "STABLE"

echo ">>> Invalidating CloudFront (${CF_DIST})"
aws cloudfront create-invalidation \
  --distribution-id "${CF_DIST}" \
  --paths '/*' \
  --query 'Invalidation.Id' \
  --output text

echo ">>> Rollback complete. Verify at https://dnz6dhrkkb5ji.cloudfront.net/"
