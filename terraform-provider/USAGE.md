# Terraform Provider for Pulsechecks

Manage your Pulsechecks monitoring infrastructure as code with Terraform.

## Installation

Add the provider to your Terraform configuration:

```hcl
terraform {
  required_providers {
    pulsechecks = {
      source  = "registry.terraform.io/abdallah/pulsechecks"
      version = "~> 1.0"
    }
  }
}

provider "pulsechecks" {
  api_url = "https://api.pulsechecks.example.com"
  token   = var.pulsechecks_token
}
```

## Configuration

### Provider Configuration

| Argument | Description | Required | Environment Variable |
|----------|-------------|----------|---------------------|
| `api_url` | Pulsechecks API URL | Yes | `PULSECHECKS_API_URL` |
| `token` | API authentication token | Yes | `PULSECHECKS_TOKEN` |

### Environment Variables

```bash
export PULSECHECKS_API_URL="https://api.pulsechecks.example.com"
export PULSECHECKS_TOKEN="your-jwt-token"
```

## Resources

### `pulsechecks_team`

Manages a Pulsechecks team.

```hcl
resource "pulsechecks_team" "production" {
  name = "Production Team"
}
```

**Arguments:**
- `name` (Required) - Team name

**Attributes:**
- `team_id` - Unique team identifier
- `created_at` - Team creation timestamp

### `pulsechecks_check`

Manages a monitoring check within a team.

```hcl
resource "pulsechecks_check" "database_backup" {
  team_id        = pulsechecks_team.production.team_id
  name           = "Database Backup"
  period_seconds = 86400  # 24 hours
  grace_seconds  = 3600   # 1 hour
}
```

**Arguments:**
- `team_id` (Required) - Team identifier
- `name` (Required) - Check name
- `period_seconds` (Required) - Expected ping interval in seconds
- `grace_seconds` (Required) - Grace period before marking as late

**Attributes:**
- `check_id` - Unique check identifier
- `token` - Ping token (sensitive)
- `status` - Current check status
- `created_at` - Check creation timestamp

## Data Sources

### `pulsechecks_team`

Read information about an existing team.

```hcl
data "pulsechecks_team" "existing" {
  team_id = "team-123"
}

output "team_name" {
  value = data.pulsechecks_team.existing.name
}
```

### `pulsechecks_checks`

List all checks for a team.

```hcl
data "pulsechecks_checks" "production_checks" {
  team_id = pulsechecks_team.production.team_id
}
```

## Examples

### Basic Setup

```hcl
# Configure the provider
terraform {
  required_providers {
    pulsechecks = {
      source  = "registry.terraform.io/abdallah/pulsechecks"
      version = "~> 1.0"
    }
  }
}

provider "pulsechecks" {
  api_url = "https://api.pulsechecks.example.com"
  token   = var.pulsechecks_token
}

# Create a team
resource "pulsechecks_team" "production" {
  name = "Production Team"
}

# Create monitoring checks
resource "pulsechecks_check" "database_backup" {
  team_id        = pulsechecks_team.production.team_id
  name           = "Database Backup"
  period_seconds = 86400  # 24 hours
  grace_seconds  = 3600   # 1 hour
}

resource "pulsechecks_check" "api_health" {
  team_id        = pulsechecks_team.production.team_id
  name           = "API Health Check"
  period_seconds = 300    # 5 minutes
  grace_seconds  = 60     # 1 minute
}

# Output the ping URLs
output "database_backup_url" {
  value = "https://api.pulsechecks.example.com/ping/${pulsechecks_check.database_backup.token}"
}

output "api_health_url" {
  value = "https://api.pulsechecks.example.com/ping/${pulsechecks_check.api_health.token}"
}
```

### Multi-Environment Setup

```hcl
# variables.tf
variable "environment" {
  description = "Environment name"
  type        = string
}

variable "pulsechecks_token" {
  description = "Pulsechecks API token"
  type        = string
  sensitive   = true
}

# main.tf
locals {
  checks = {
    "database-backup" = {
      name           = "Database Backup"
      period_seconds = 86400
      grace_seconds  = 3600
    }
    "api-health" = {
      name           = "API Health"
      period_seconds = 300
      grace_seconds  = 60
    }
    "log-processing" = {
      name           = "Log Processing Job"
      period_seconds = 1800
      grace_seconds  = 300
    }
  }
}

resource "pulsechecks_team" "environment" {
  name = "${title(var.environment)} Team"
}

resource "pulsechecks_check" "checks" {
  for_each = local.checks

  team_id        = pulsechecks_team.environment.team_id
  name           = "${local.checks[each.key].name} (${var.environment})"
  period_seconds = local.checks[each.key].period_seconds
  grace_seconds  = local.checks[each.key].grace_seconds
}

# Generate ping URLs for each check
output "ping_urls" {
  value = {
    for key, check in pulsechecks_check.checks :
    key => "https://api.pulsechecks.example.com/ping/${check.token}"
  }
  sensitive = true
}
```

### Integration with Existing Infrastructure

```hcl
# Use with existing AWS infrastructure
data "aws_ssm_parameter" "pulsechecks_token" {
  name = "/pulsechecks/api-token"
}

provider "pulsechecks" {
  api_url = "https://api.pulsechecks.example.com"
  token   = data.aws_ssm_parameter.pulsechecks_token.value
}

# Create checks for AWS resources
resource "pulsechecks_check" "rds_backup" {
  team_id        = pulsechecks_team.aws.team_id
  name           = "RDS Backup - ${aws_db_instance.main.identifier}"
  period_seconds = 86400
  grace_seconds  = 7200
}

# Use in Lambda function environment
resource "aws_lambda_function" "backup_job" {
  # ... other configuration ...
  
  environment {
    variables = {
      PULSECHECKS_PING_URL = "https://api.pulsechecks.example.com/ping/${pulsechecks_check.rds_backup.token}"
    }
  }
}
```

### Workspace-Based Configuration

```hcl
# Use Terraform workspaces for different environments
locals {
  environment_config = {
    dev = {
      team_name = "Development Team"
      api_url   = "https://dev-api.pulsechecks.example.com"
    }
    staging = {
      team_name = "Staging Team"
      api_url   = "https://staging-api.pulsechecks.example.com"
    }
    prod = {
      team_name = "Production Team"
      api_url   = "https://api.pulsechecks.example.com"
    }
  }
  
  current_env = local.environment_config[terraform.workspace]
}

provider "pulsechecks" {
  api_url = local.current_env.api_url
  token   = var.pulsechecks_token
}

resource "pulsechecks_team" "current" {
  name = local.current_env.team_name
}
```

## Common Patterns

### 1. Ping URL Generation

```hcl
locals {
  ping_urls = {
    for key, check in pulsechecks_check.monitoring :
    key => "https://api.pulsechecks.example.com/ping/${check.token}"
  }
}

# Store in AWS Systems Manager
resource "aws_ssm_parameter" "ping_urls" {
  for_each = local.ping_urls
  
  name  = "/monitoring/ping-urls/${each.key}"
  type  = "SecureString"
  value = each.value
}
```

### 2. Check Configuration from YAML

```hcl
locals {
  checks_config = yamldecode(file("${path.module}/checks.yaml"))
}

resource "pulsechecks_check" "from_config" {
  for_each = local.checks_config.checks

  team_id        = pulsechecks_team.main.team_id
  name           = each.value.name
  period_seconds = each.value.period_seconds
  grace_seconds  = each.value.grace_seconds
}
```

With `checks.yaml`:
```yaml
checks:
  database_backup:
    name: "Database Backup"
    period_seconds: 86400
    grace_seconds: 3600
  api_health:
    name: "API Health Check"
    period_seconds: 300
    grace_seconds: 60
```

### 3. Integration with CI/CD

```hcl
# Create checks for CI/CD jobs
resource "pulsechecks_check" "deploy_job" {
  team_id        = pulsechecks_team.cicd.team_id
  name           = "Deploy Job - ${var.service_name}"
  period_seconds = var.deploy_frequency
  grace_seconds  = 1800  # 30 minutes
}

# Output for CI/CD variables
output "deploy_ping_url" {
  value     = "https://api.pulsechecks.example.com/ping/${pulsechecks_check.deploy_job.token}"
  sensitive = true
}
```

## Best Practices

1. **Use variables** for sensitive tokens
2. **Store ping URLs** in secure parameter stores
3. **Use for_each** for multiple similar checks
4. **Tag resources** with environment/team information
5. **Use data sources** to reference existing teams
6. **Version pin** the provider for stability

## Troubleshooting

### Provider Not Found
Ensure the provider is properly installed:
```bash
terraform providers
```

### Authentication Errors
Verify your token has proper permissions:
```bash
curl -H "Authorization: Bearer $PULSECHECKS_TOKEN" \
     https://api.pulsechecks.example.com/me
```

### API Connectivity
Test API connectivity:
```bash
curl -I https://api.pulsechecks.example.com/health
```
