"""Network primitives for the P&ID demo.

Builds an isolated VPC with a public subnet (NAT egress) + a private
subnet for ECS Fargate. Bedrock and CloudWatch traffic stays on the
AWS network via interface endpoints; S3 uses a gateway endpoint.

Stateful by intent: termination protection ON. The data plane (ECS
tasks, ALB) lives in the AppStack and can be torn down/rebuilt without
disturbing the VPC.
"""
from __future__ import annotations

from aws_cdk import Stack, RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_logs as logs
from constructs import Construct


class NetworkStack(Stack):
    """VPC + endpoints. Other stacks consume `self.vpc`."""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        self.template_options.description = (
            "P&ID demo network: 2-AZ VPC with private ECS subnets and "
            "interface endpoints for Bedrock and CloudWatch."
        )

        flow_log_group = logs.LogGroup(
            self,
            "VpcFlowLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.40.0.0/20"),
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
            nat_gateways=1,
            flow_logs={
                "all": ec2.FlowLogOptions(
                    destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                        log_group=flow_log_group
                    ),
                    traffic_type=ec2.FlowLogTrafficType.ALL,
                )
            },
            restrict_default_security_group=True,
        )

        # Gateway endpoint for S3 (free; required for Bedrock model artifacts).
        self.vpc.add_gateway_endpoint(
            "S3GwEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        endpoint_sg = ec2.SecurityGroup(
            self,
            "EndpointsSg",
            vpc=self.vpc,
            description="VPC endpoint security group - allows TLS from VPC CIDR",
            allow_all_outbound=False,
        )
        endpoint_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="TLS from inside the VPC",
        )

        # Interface endpoints — Bedrock + Bedrock Runtime + CloudWatch logs.
        for label, service in [
            ("BedrockRuntime", ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME),
            ("Bedrock", ec2.InterfaceVpcEndpointAwsService.BEDROCK),
            ("CloudWatchLogs", ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS),
            ("EcrApi", ec2.InterfaceVpcEndpointAwsService.ECR),
            ("EcrDkr", ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER),
        ]:
            self.vpc.add_interface_endpoint(
                f"{label}Endpoint",
                service=service,
                private_dns_enabled=True,
                security_groups=[endpoint_sg],
                subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ),
            )
