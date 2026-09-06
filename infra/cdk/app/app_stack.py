"""Application stack: ECS Fargate + ALB + CloudFront.

Security posture:
  - ECS tasks run in private subnets, no public IP.
  - ALB security group allows ingress ONLY from CloudFront's managed
    prefix list (`pl-82a045eb` in us-east-1) on port 80. We pass
    `open=False` to add_listener so CDK does not silently insert
    `0.0.0.0/0` ingress, which security scanners flag and revoke.
  - CloudFront -> ALB origin. Public traffic NEVER touches the ALB
    directly; the SG would refuse any other source.
  - The Bedrock IAM grant is scoped to the configured model IDs, not
    `*`, so the runtime role can only invoke models we expect.

`cdk-nag` (AwsSolutionsChecks) is wired up at the App level (see
app.py) to enforce additional best-practice checks at synth time.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

LAMBDA_EDGE_DIR = Path(__file__).resolve().parent / "lambda_edge"

# CloudFront managed prefix list (for "from CloudFront" SG ingress).
# The ID is account/region-scoped, so we look it up at synth time via
# the AWS-managed prefix list service name. See:
# https://docs.aws.amazon.com/vpc/latest/userguide/working-with-aws-managed-prefix-lists.html
CLOUDFRONT_ORIGIN_FACING_PL_NAME = (
    "com.amazonaws.global.cloudfront.origin-facing"
)


class AppStack(Stack):
    """ECS Fargate service fronted by an internal ALB + CloudFront."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        vpc: Optional[ec2.IVpc] = None,
        existing_vpc_id: Optional[str] = None,
        bedrock_model_ids: Sequence[str],
        bedrock_region: str,
        image_tag: str = "latest",
        cpu: int = 1024,
        memory_mib: int = 2048,
        desired_count: int = 1,
        agentcore_runtime_arn: Optional[str] = None,
        agentcore_vision_arn: Optional[str] = None,
        agentcore_ocr_arn: Optional[str] = None,
        agentcore_fusion_arn: Optional[str] = None,
        agentcore_summary_arn: Optional[str] = None,
        agentcore_memory_id: Optional[str] = None,
        agentcore_harness_arn: Optional[str] = None,
        user_pool: Optional[cognito.IUserPool] = None,
        user_pool_client_id: Optional[str] = None,
        hosted_ui_domain: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)
        self.template_options.description = (
            "P&ID demo data plane: ECR repo, ECS Fargate service, "
            "internal ALB locked to the CloudFront prefix list, and a "
            "CloudFront distribution as the public entry point."
        )

        if vpc is None:
            if not existing_vpc_id:
                raise ValueError("AppStack needs either `vpc` or `existing_vpc_id`")
            vpc = ec2.Vpc.from_lookup(self, "ImportedVpc", vpc_id=existing_vpc_id)

        # ---- ECR repository ---------------------------------------------
        repo = ecr.Repository(
            self,
            "ContainerRepo",
            repository_name="pnid-demo",
            image_scan_on_push=True,
            image_tag_mutability=ecr.TagMutability.MUTABLE,
            encryption=ecr.RepositoryEncryption.AES_256,
            # DESTROY (with empty_on_delete=True) so a failed first
            # rollout does not leave an orphan that blocks the next
            # `cdk deploy`. Production should switch to RETAIN.
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

        # ---- ECS cluster + task -----------------------------------------
        cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
            enable_fargate_capacity_providers=True,
        )

        log_group = logs.LogGroup(
            self,
            "TaskLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="Execution identity for the P&ID demo Fargate task",
        )
        # Bedrock invoke grant.
        # Inference profiles like "us.cohere.embed-v4:0" or
        # "global.anthropic.claude-opus-4-7" forward to the underlying
        # foundation model whose ARN strips the geography prefix
        # ("us.", "global.", etc.). The agent code may invoke either ARN
        # form, so we grant both for the configured models. Cross-region
        # inference profiles can also fan out to all-region foundation
        # model ARNs, so we use region "*" for the stripped form.
        def _strip_prefix(model_id: str) -> str:
            for prefix in ("us.", "eu.", "apac.", "global."):
                if model_id.startswith(prefix):
                    return model_id[len(prefix):]
            return model_id

        bedrock_resources: list[str] = []
        for model_id in bedrock_model_ids:
            bedrock_resources.append(
                self.format_arn(
                    service="bedrock",
                    region=bedrock_region,
                    account="",
                    resource="foundation-model",
                    resource_name=model_id,
                )
            )
            stripped = _strip_prefix(model_id)
            if stripped != model_id:
                bedrock_resources.append(
                    self.format_arn(
                        service="bedrock",
                        region="*",
                        account="",
                        resource="foundation-model",
                        resource_name=stripped,
                    )
                )
            bedrock_resources.append(
                self.format_arn(
                    service="bedrock",
                    region=bedrock_region,
                    resource="inference-profile",
                    resource_name=model_id,
                )
            )
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                ],
                resources=bedrock_resources,
            )
        )
        # Allow listing inference profiles (read-only) so the agent can
        # discover region-specific profile IDs at boot.
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:ListFoundationModels",
                    "bedrock:ListInferenceProfiles",
                ],
                resources=["*"],
            )
        )

        # Textract — used by the OCR agent for pixel-precise label boxes.
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "textract:DetectDocumentText",
                    "textract:AnalyzeDocument",
                ],
                resources=["*"],
            )
        )

        # AgentCore Memory (cross-session recall) and Harness (preview).
        # Both APIs share the `bedrock-agentcore:` namespace.
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:CreateMemory",
                    "bedrock-agentcore:InvokeHarness",
                ],
                resources=["*"],
            )
        )

        # AgentCore Runtime invoke. The actual ARN segment is `runtime/`
        # (singular), not `agent-runtime/` — pnidvision/pnidocr/pnidfusion/
        # pnidsummary all live under `arn:...:runtime/<name>-<id>`. Grant
        # to all runtimes in this account+region so swapping or adding
        # runtime ARNs at deploy time does not require an IAM round-trip.
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                ],
                resources=[
                    self.format_arn(
                        service="bedrock-agentcore",
                        resource="runtime",
                        resource_name="*",
                    ),
                    self.format_arn(
                        service="bedrock-agentcore",
                        resource="runtime",
                        resource_name="*/runtime-endpoint/*",
                    ),
                ],
            )
        )

        execution_role = iam.Role(
            self,
            "ExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        task = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            cpu=cpu,
            memory_limit_mib=memory_mib,
            task_role=task_role,
            execution_role=execution_role,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )
        container_env: dict[str, str] = {"AWS_REGION": bedrock_region}
        if agentcore_runtime_arn:
            container_env["BEDROCK_AGENTCORE_RUNTIME_ARN"] = agentcore_runtime_arn
        if agentcore_vision_arn:
            container_env["AGENTCORE_VISION_ARN"] = agentcore_vision_arn
        if agentcore_ocr_arn:
            container_env["AGENTCORE_OCR_ARN"] = agentcore_ocr_arn
        if agentcore_fusion_arn:
            container_env["AGENTCORE_FUSION_ARN"] = agentcore_fusion_arn
        if agentcore_summary_arn:
            container_env["AGENTCORE_SUMMARY_ARN"] = agentcore_summary_arn
        if agentcore_memory_id:
            container_env["BEDROCK_AGENTCORE_MEMORY_ID"] = agentcore_memory_id
        if agentcore_harness_arn:
            container_env["AGENTCORE_HARNESS_ARN"] = agentcore_harness_arn

        task.add_container(
            "App",
            image=ecs.ContainerImage.from_ecr_repository(repo, image_tag),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="pnid-demo", log_group=log_group
            ),
            port_mappings=[ecs.PortMapping(container_port=8000)],
            environment=container_env,
            health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL",
                    "python -c 'import urllib.request,sys;"
                    "sys.exit(0 if urllib.request.urlopen(\"http://localhost:8000/api/health\",timeout=2).status==200 else 1)'",
                ],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(30),
            ),
            essential=True,
        )

        service_sg = ec2.SecurityGroup(
            self,
            "ServiceSg",
            vpc=vpc,
            description=(
                "Fargate task SG. Egress is intentionally NOT default-open: "
                "explicit rules allow HTTPS to VPC endpoints (Bedrock, "
                "CloudWatch, ECR), AgentCore Runtime, and DNS to the VPC "
                "resolver. No 0.0.0.0/0 wide-open outbound."
            ),
            allow_all_outbound=False,
        )

        # HTTPS to VPC interface endpoints (Bedrock Runtime, Bedrock,
        # CloudWatch Logs, ECR API/Docker). Endpoints accept TLS only.
        service_sg.add_egress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="HTTPS to VPC endpoints inside the VPC",
        )
        # DNS to the VPC's .2 resolver (UDP + TCP) for endpoint name lookup.
        service_sg.add_egress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.udp(53),
            description="DNS UDP to VPC resolver",
        )
        service_sg.add_egress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(53),
            description="DNS TCP to VPC resolver",
        )
        # AgentCore Runtime + AgentCore Memory are public AWS endpoints
        # that don't yet have us-east-1 interface endpoints; allow HTTPS
        # to the AWS managed prefix list "com.amazonaws.us-east-1.s3"
        # (via S3 gateway endpoint covers S3) and let HTTPS egress to
        # 0.0.0.0/0 via NAT for the bedrock-agentcore data plane.
        # Scoped to TCP/443 only — never wide-open.
        service_sg.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description=(
                "HTTPS only to AWS public endpoints "
                "(bedrock-agentcore, bedrock-agentcore-control)"
            ),
        )

        service = ecs.FargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task,
            desired_count=desired_count,
            assign_public_ip=False,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[service_sg],
            min_healthy_percent=100,
            max_healthy_percent=200,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )

        # ---- ALB (internal-only ingress from CloudFront prefix list) -----
        alb_sg = ec2.SecurityGroup(
            self,
            "AlbSg",
            vpc=vpc,
            description="ALB SG - allows port 80 ONLY from CloudFront prefix list",
            allow_all_outbound=False,
        )
        cloudfront_pl = ec2.PrefixList.from_lookup(
            self,
            "CloudFrontOriginPrefixList",
            prefix_list_name=CLOUDFRONT_ORIGIN_FACING_PL_NAME,
        )
        alb_sg.add_ingress_rule(
            peer=ec2.Peer.prefix_list(cloudfront_pl.prefix_list_id),
            connection=ec2.Port.tcp(80),
            description="From CloudFront managed prefix list",
        )
        alb_sg.add_egress_rule(
            peer=service_sg,
            connection=ec2.Port.tcp(8000),
            description="To Fargate target on container port",
        )
        service_sg.add_ingress_rule(
            peer=alb_sg,
            connection=ec2.Port.tcp(8000),
            description="From ALB on container port",
        )

        alb = elbv2.ApplicationLoadBalancer(
            self,
            "Alb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg,
            ip_address_type=elbv2.IpAddressType.IPV4,
            # Long live extractions can take >2 min; default 60s would
            # close the WebSocket mid-flight. 600s comfortably covers
            # the worst-case Textract + Vision + self-correct path.
            idle_timeout=Duration.seconds(600),
        )

        target_group = elbv2.ApplicationTargetGroup(
            self,
            "AppTg",
            vpc=vpc,
            target_type=elbv2.TargetType.IP,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            health_check=elbv2.HealthCheck(
                path="/api/health",
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
                interval=Duration.seconds(15),
                timeout=Duration.seconds(5),
                healthy_http_codes="200",
            ),
            deregistration_delay=Duration.seconds(15),
        )
        service.attach_to_application_target_group(target_group)

        # CRITICAL: open=False so CDK does not auto-add 0.0.0.0/0 ingress.
        alb.add_listener(
            "HttpListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            open=False,
            default_target_groups=[target_group],
        )

        # ---- Lambda@Edge auth gate (optional) ---------------------------
        edge_associations: list[cloudfront.EdgeLambda] = []
        if user_pool and user_pool_client_id and hosted_ui_domain:
            # Inject the Cognito identifiers into the function source at
            # synth time. Lambda@Edge does not allow environment variables
            # because the function is replicated to edge locations.
            tpl = (LAMBDA_EDGE_DIR / "auth.template.js").read_text()
            # Placeholder substitution — single-pass, fail-loud if any
            # placeholder is missing so we never deploy an unpatched build.
            substitutions = {
                "__USER_POOL_ID__": user_pool.user_pool_id,
                "__APP_CLIENT_ID__": user_pool_client_id,
                "__HOSTED_UI_HOSTNAME__": hosted_ui_domain,
                "__REGION__": self.region,
            }
            patched = tpl
            for placeholder, value in substitutions.items():
                if placeholder not in patched:
                    raise RuntimeError(
                        f"Lambda@Edge template missing placeholder: {placeholder}"
                    )
                patched = patched.replace(placeholder, value)

            # Lambda@Edge supported runtimes (as of 2026-05) are Node 18 / 20.
            # Newer runtimes are not yet whitelisted at edge, so we pin to
            # NODEJS_20_X here even though regional Lambda would default to 22.
            edge_fn = lambda_.Function(
                self,
                "AuthEdgeFn",
                runtime=lambda_.Runtime.NODEJS_20_X,
                # `from_inline` packages the code as `index.js`, not
                # `auth.js`, so the handler must reference index.
                handler="index.handler",
                code=lambda_.Code.from_inline(patched),
                timeout=Duration.seconds(5),
                memory_size=128,
                description="Cognito Hosted UI gate for the P&ID demo",
                # Lambda@Edge requires no env vars and a versioned function.
            )
            edge_version = edge_fn.current_version
            edge_associations = [
                cloudfront.EdgeLambda(
                    function_version=edge_version,
                    event_type=cloudfront.LambdaEdgeEventType.VIEWER_REQUEST,
                    include_body=False,
                ),
            ]

        # ---- CloudFront distribution ------------------------------------
        # Origin uses HTTP because TLS terminates at CloudFront. End-to-end
        # TLS would require an ACM cert + custom domain, which the demo
        # leaves to the deployer.
        distribution = cloudfront.Distribution(
            self,
            "Cdn",
            comment="P&ID demo distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(
                    alb,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                    http_port=80,
                    origin_shield_enabled=False,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
                edge_lambdas=edge_associations,
            ),
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            http_version=cloudfront.HttpVersion.HTTP2,
        )


        # ---- Outputs ----------------------------------------------------
        CfnOutput(
            self,
            "RepoUri",
            value=repo.repository_uri,
            description="ECR repo for pushing the image (tag must match the deploy)",
        )
        CfnOutput(
            self,
            "DistributionDomain",
            value=distribution.distribution_domain_name,
            description="CloudFront URL (public entry point)",
        )
        CfnOutput(
            self,
            "AlbDns",
            value=alb.load_balancer_dns_name,
            description="ALB DNS - private (only reachable from CloudFront)",
        )
        CfnOutput(
            self,
            "ClusterName",
            value=cluster.cluster_name,
            description="ECS cluster name",
        )
        CfnOutput(
            self,
            "ServiceName",
            value=service.service_name,
            description="ECS Fargate service name",
        )

        self.repo = repo
        self.distribution = distribution
