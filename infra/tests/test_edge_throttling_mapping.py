"""Regression tests for provider-specific edge throttling mapping."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def test_aws_api_gateway_throttling_uses_variables():
    api_gateway = read("infra/aws/api-gateway.tf")
    variables = read("infra/aws/variables.tf")

    assert 'variable "api_gateway_throttling_rate_limit"' in variables
    assert 'variable "api_gateway_throttling_burst_limit"' in variables
    assert 'default_route_settings' in api_gateway
    assert 'throttling_rate_limit  = var.api_gateway_throttling_rate_limit' in api_gateway
    assert 'throttling_burst_limit = var.api_gateway_throttling_burst_limit' in api_gateway


def test_gcp_edge_throttling_includes_lb_and_cloud_armor():
    edge = read("infra/gcp/edge_throttling.tf")

    assert 'google_compute_security_policy" "api_edge"' in edge
    assert 'google_compute_backend_service" "api_edge"' in edge
    assert 'google_compute_global_forwarding_rule" "api_edge"' in edge
    assert 'google_compute_managed_ssl_certificate" "api_edge"' in edge
    assert 'google_compute_region_network_endpoint_group" "api_edge"' in edge


def test_gcp_public_cloud_run_access_is_explicit_when_edge_throttling_is_disabled():
    cloudrun = read("infra/gcp/cloudrun.tf")

    assert 'google_cloud_run_service_iam_member' in cloudrun
    assert 'public_access' in cloudrun
    assert 'count    = var.enable_custom_domain_mapping && !var.edge_throttling_enabled ? 1 : 0' in cloudrun
    assert 'count        = local.create_dns_records && !var.edge_throttling_enabled ? 1 : 0' in cloudrun
    assert 'Cloud Run access remains direct' in read("infra/gcp/outputs.tf") or 'Cloud Run access remains direct' in cloudrun


def test_docs_describe_edge_throttling_by_provider():
    operations = read("docs/operations.md")
    architecture = read("docs/multi-cloud-architecture.md")

    assert 'AWS production: API Gateway stage throttling is the primary edge control.' in operations
    assert 'GCP production: Cloud Armor in front of a global HTTPS load balancer is the primary edge control.' in operations
    assert '- **AWS**: API Gateway throttling, WAF optional' in architecture
    assert '- **GCP**: Cloud Armor requires the external HTTPS load balancer path' in architecture
