"""CloudWatch metrics for monitoring and observability."""
import boto3
from typing import Dict, Any, Optional
from datetime import datetime
from .config import get_settings
from .logging_config import get_logger

logger = get_logger(__name__)


class MetricsClient:
    """CloudWatch metrics client for Pulsechecks."""
    
    def __init__(self):
        self.settings = get_settings()
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.settings.aws_region)
        self.namespace = 'Pulsechecks'
    
    def put_metric(self, metric_name: str, value: float, unit: str = 'Count', 
                   dimensions: Optional[Dict[str, str]] = None):
        """Put a custom metric to CloudWatch."""
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.utcnow()
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
            
            logger.debug(f"Metric sent: {metric_name}={value} {unit}", extra={
                'extra_fields': {'metric_name': metric_name, 'value': value, 'unit': unit}
            })
            
        except Exception as e:
            logger.error(f"Failed to send metric {metric_name}: {str(e)}", exc_info=True)
    
    def increment_counter(self, metric_name: str, dimensions: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        self.put_metric(metric_name, 1.0, 'Count', dimensions)
    
    def record_duration(self, metric_name: str, duration_ms: float, 
                       dimensions: Optional[Dict[str, str]] = None):
        """Record a duration metric."""
        self.put_metric(metric_name, duration_ms, 'Milliseconds', dimensions)
    
    # Business metrics
    def check_created(self, team_id: str):
        """Record check creation."""
        self.increment_counter('CheckCreated', {'TeamId': team_id})
    
    def check_deleted(self, team_id: str):
        """Record check deletion."""
        self.increment_counter('CheckDeleted', {'TeamId': team_id})
    
    def ping_received(self, team_id: str, check_id: str, success: bool):
        """Record ping received."""
        status = 'Success' if success else 'Failed'
        self.increment_counter('PingReceived', {
            'TeamId': team_id, 
            'CheckId': check_id, 
            'Status': status
        })
    
    def alert_sent(self, team_id: str, check_id: str, alert_type: str, success: bool):
        """Record alert sent."""
        status = 'Success' if success else 'Failed'
        self.increment_counter('AlertSent', {
            'TeamId': team_id,
            'CheckId': check_id,
            'AlertType': alert_type,
            'Status': status
        })
    
    def late_detection_run(self, checks_processed: int, alerts_queued: int):
        """Record late detection run."""
        self.put_metric('ChecksProcessed', checks_processed, 'Count')
        self.put_metric('AlertsQueued', alerts_queued, 'Count')
    
    def api_request(self, method: str, path: str, status_code: int, duration_ms: float):
        """Record API request metrics."""
        dimensions = {
            'Method': method,
            'Path': path,
            'StatusCode': str(status_code)
        }
        
        self.increment_counter('APIRequest', dimensions)
        self.record_duration('APILatency', duration_ms, dimensions)
        
        # Record error rate
        if status_code >= 400:
            self.increment_counter('APIError', dimensions)


# Global metrics client instance
_metrics_client = None

def get_metrics_client() -> MetricsClient:
    """Get the global metrics client instance."""
    global _metrics_client
    if _metrics_client is None:
        _metrics_client = MetricsClient()
    return _metrics_client
