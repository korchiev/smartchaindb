"""
BigchainDB Validation Metrics Endpoint

Provides real-time performance metrics for SHACL validation caching.
"""

from flask import Blueprint, jsonify, request
from flask_restful import reqparse, Resource, Api
from bigchaindb.common.shacl_validator_cached import get_shacl_validator
import logging

logger = logging.getLogger(__name__)

# Create Blueprint
validation_metrics_views = Blueprint('validation_metrics_views', __name__)
validation_metrics_api = Api(validation_metrics_views)


class ValidationMetricsAPI(Resource):
    """
    Endpoint for SHACL validation performance metrics.
    
    GET /api/v1/metrics/validation
    Returns comprehensive validation performance statistics.
    """
    
    def get(self):
        """Get validation performance metrics."""
        try:
            validator = get_shacl_validator()
            
            # Get comprehensive metrics
            metrics = validator.get_metrics_summary()
            cache_stats = validator.get_cache_stats()
            
            # Check service health
            shacl_healthy = validator.health_check()
            
            return {
                'status': 'success',
                'shacl_service_healthy': shacl_healthy,
                'metrics': metrics,
                'cache': cache_stats,
                'recommendations': _generate_recommendations(metrics, cache_stats)
            }, 200
            
        except Exception as e:
            logger.error(f"Error retrieving validation metrics: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }, 500


class ValidationCacheControlAPI(Resource):
    """
    Endpoint for cache management operations.
    
    POST /api/v1/metrics/validation/cache/clear
    Clears the validation cache (admin operation).
    """
    
    def post(self):
        """Clear the validation cache."""
        try:
            validator = get_shacl_validator()
            
            # Get stats before clearing
            before_stats = validator.get_cache_stats()
            
            # Clear cache
            validator.clear_cache()
            
            # Get stats after clearing
            after_stats = validator.get_cache_stats()
            
            logger.info(f"Validation cache cleared: {before_stats['cache_size']} entries removed")
            
            return {
                'status': 'success',
                'message': 'Cache cleared successfully',
                'before': before_stats,
                'after': after_stats
            }, 200
            
        except Exception as e:
            logger.error(f"Error clearing validation cache: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }, 500


class ValidationMetricsResetAPI(Resource):
    """
    Endpoint for resetting metrics (testing/debugging).
    
    POST /api/v1/metrics/validation/reset
    Resets all validation metrics to zero.
    """
    
    def post(self):
        """Reset validation metrics."""
        try:
            validator = get_shacl_validator()
            validator.metrics.reset_metrics()
            
            logger.info("Validation metrics reset")
            
            return {
                'status': 'success',
                'message': 'Metrics reset successfully'
            }, 200
            
        except Exception as e:
            logger.error(f"Error resetting validation metrics: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }, 500


def _generate_recommendations(metrics: dict, cache_stats: dict) -> list:
    """Generate performance recommendations based on metrics."""
    recommendations = []
    
    if metrics == {'message': 'No validations recorded yet'}:
        return ['System just started - metrics will be available after first validations']
    
    # Check cache hit rate
    cache_hit_rate = metrics.get('cache_hit_rate_percent', 0)
    if cache_hit_rate < 50:
        recommendations.append(
            f"Cache hit rate is low ({cache_hit_rate:.1f}%). "
            "Consider increasing cache_ttl if transactions are being re-validated."
        )
    elif cache_hit_rate > 90:
        recommendations.append(
            f"Excellent cache hit rate ({cache_hit_rate:.1f}%)! "
            "Caching is working optimally."
        )
    
    # Check cache utilization
    cache_utilization = cache_stats.get('cache_utilization_percent', 0)
    if cache_utilization > 90:
        recommendations.append(
            f"Cache is {cache_utilization:.1f}% full. "
            "Consider increasing cache_max_size to reduce evictions."
        )
    
    # Check evictions
    evictions = metrics.get('cache_evictions', 0)
    if evictions > 100:
        recommendations.append(
            f"High number of cache evictions ({evictions}). "
            "Increase cache_max_size to improve performance."
        )
    
    # Check validation errors
    errors = metrics.get('validation_errors', 0)
    total = metrics.get('total_validations', 1)
    error_rate = (errors / total * 100) if total > 0 else 0
    if error_rate > 10:
        recommendations.append(
            f"High validation error rate ({error_rate:.1f}%). "
            "Check transaction submissions or SHACL shapes."
        )
    
    # Check performance
    perf = metrics.get('performance', {})
    avg_time = perf.get('avg_time_ms', 0)
    if avg_time > 100:
        recommendations.append(
            f"Average validation time is high ({avg_time:.1f}ms). "
            "Check SHACL service performance and MongoDB indexes."
        )
    
    # Time savings
    time_saved = perf.get('time_saved_by_cache_ms', 0)
    if time_saved > 1000:
        recommendations.append(
            f"Caching has saved {time_saved:.0f}ms total! "
            "Keep cache enabled for optimal performance."
        )
    
    if not recommendations:
        recommendations.append("System is performing normally. No issues detected.")
    
    return recommendations


# Register API endpoints
validation_metrics_api.add_resource(
    ValidationMetricsAPI,
    '/api/v1/metrics/validation',
    strict_slashes=False
)

validation_metrics_api.add_resource(
    ValidationCacheControlAPI,
    '/api/v1/metrics/validation/cache/clear',
    strict_slashes=False
)

validation_metrics_api.add_resource(
    ValidationMetricsResetAPI,
    '/api/v1/metrics/validation/reset',
    strict_slashes=False
)


