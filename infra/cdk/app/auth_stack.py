"""Cognito user pool for the demo's CloudFront access gate.

The pool is a thin "presenter login" — a single user pool with a single
app client, no federation. The presenter (and any approved viewers) sign
in via the Hosted UI; CloudFront's Lambda@Edge function then verifies
the resulting cookie on every request.

This is decoupled from the AppStack so the user pool's lifecycle is
independent of the data plane (we may rebuild ECS+ALB+CloudFront
multiple times during a demo cycle without losing user accounts).
"""
from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class AuthStack(Stack):
    def __init__(self, scope: Construct, id: str, *, callback_urls: list[str] = None, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        self.template_options.description = (
            "Cognito User Pool guarding CloudFront for the P&ID demo. "
            "Used by Lambda@Edge to verify viewer requests."
        )

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="pnid-demo-presenter",
            self_sign_up_enabled=False,  # presenter creates accounts manually
            sign_in_aliases=cognito.SignInAliases(email=True, username=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=False),
            ),
            password_policy=cognito.PasswordPolicy(
                # 8 chars to allow the demo's "Passw0rd1!" preset.
                # Tighten to 12+ for production.
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=False),
            # `advanced_security_mode` is deprecated — the new API splits
            # into standard + custom threat protection modes. We pick AUDIT
            # for both (no enforce) since this is an internal demo.
            standard_threat_protection_mode=cognito.StandardThreatProtectionMode.AUDIT_ONLY,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Add Hosted UI domain — Cognito-prefixed (cheap, no ACM cert needed).
        self.user_pool_domain = self.user_pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix="pnid-demo-" + self.account[-6:],
            ),
        )

        callback_urls = callback_urls or ["https://example.invalid/callback"]
        logout_urls = [u.replace("/callback", "/") for u in callback_urls]

        self.app_client = self.user_pool.add_client(
            "WebClient",
            user_pool_client_name="pnid-demo-web",
            generate_secret=False,  # public SPA-style client used by L@E
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
                callback_urls=callback_urls,
                logout_urls=logout_urls,
            ),
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(7),
            prevent_user_existence_errors=True,
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO,
            ],
        )

        # Outputs that downstream stacks (and Lambda@Edge build) consume.
        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            export_name=f"{id}-UserPoolId",
        )
        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.app_client.user_pool_client_id,
            export_name=f"{id}-UserPoolClientId",
        )
        CfnOutput(
            self,
            "HostedUiDomain",
            value=self.user_pool_domain.domain_name,
            export_name=f"{id}-HostedUiDomain",
            description="Cognito Hosted UI prefix domain (use as oauth issuer host)",
        )
