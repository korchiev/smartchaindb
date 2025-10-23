"""
Enhanced Validation Metrics API with State-Aware Cache Statistics

This module provides comprehensive metrics for the state-aware caching system,
including cache invalidation events and state dependency tracking.
"""

import logging
from flask import Blueprint, jsonify, request
from bigchaindb.common.shacl_validator_state_aware import get_state_aware_shacl_validator
from bigchaindb.common.cache_invalidation import get_event_bus

logger = logging.getLogger(__name__)

# Create Blueprint for validation metrics
validation_metrics_bp = Blueprint('validation_metrics', __name__)


@validation_metrics_bp.route('/api/v1/metrics/validation', methods=['GET'])
def get_validation_metrics():
    """
    Get comprehensive validation metrics including state-aware cache statistics.
    """
    try:
        validator = get_state_aware_shacl_validator()
        event_bus = get_event_bus()
        
        # Get basic validator metrics
        validator_stats = validator.get_cache_stats()
        
        # Check SHACL service health
        shacl_healthy = validator.health_check()
        
        # Get event bus statistics
        event_stats = {
            'event_queue_size': len(event_bus._event_queue),
            'registered_handlers': len(event_bus._handlers.get('state_change', [])),
            'event_processing_active': event_bus._running
        }
        
        # Compile comprehensive metrics
        metrics = {
            'status': 'success',
            'shacl_service_healthy': shacl_healthy,
            'cache_enabled': validator.cache_enabled,
            'state_aware_caching': True,
            'cache_statistics': validator_stats,
            'event_system': event_stats,
            'recommendations': _generate_recommendations(validator_stats, event_stats)
        }
        
        return jsonify(metrics)
    
    except Exception as e:
        logger.error(f"Error getting validation metrics: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to get metrics: {str(e)}'
        }), 500


@validation_metrics_bp.route('/api/v1/metrics/validation/cache/clear', methods=['POST'])
def clear_cache():
    """
    Clear all cached validation results.
    """
    try:
        validator = get_state_aware_shacl_validator()
        validator.clear_cache()
        
        logger.info("Cache cleared via API request")
        
        return jsonify({
            'status': 'success',
            'message': 'Cache cleared successfully'
        })
    
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear cache: {str(e)}'
        }), 500


@validation_metrics_bp.route('/api/v1/metrics/validation/cache/invalidate', methods=['POST'])
def invalidate_specific_cache():
    """
    Invalidate cache entries for specific entities.
    
    Expected JSON body:
    {
        "entity_type": "advertisement|buy_offer|asset|sell|return_request|creator|advertiser",
        "entity_id": "entity_identifier"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'JSON body required'
            }), 400
        
        entity_type = data.get('entity_type')
        entity_id = data.get('entity_id')
        
        if not entity_type or not entity_id:
            return jsonify({
                'status': 'error',
                'message': 'entity_type and entity_id required'
            }), 400
        
        validator = get_state_aware_shacl_validator()
        
        if entity_type == 'advertisement':
            validator.invalidate_advertisement_cache(entity_id)
        elif entity_type == 'buy_offer':
            validator.invalidate_buy_offer_cache(entity_id)
        elif entity_type == 'asset':
            validator.invalidate_asset_cache(entity_id)
        elif entity_type == 'sell':
            validator.invalidate_sell_cache(entity_id)
        elif entity_type == 'return_request':
            validator.invalidate_return_request_cache(entity_id)
        elif entity_type == 'creator':
            validator.invalidate_creator_cache(entity_id)
        elif entity_type == 'advertiser':
            validator.invalidate_advertiser_cache(entity_id)
        else:
            return jsonify({
                'status': 'error',
                'message': f'Invalid entity_type: {entity_type}'
            }), 400
        
        logger.info(f"Cache invalidated for {entity_type}:{entity_id}")
        
        return jsonify({
            'status': 'success',
            'message': f'Cache invalidated for {entity_type}:{entity_id}'
        })
    
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to invalidate cache: {str(e)}'
        }), 500


@validation_metrics_bp.route('/api/v1/metrics/validation/events', methods=['GET'])
def get_event_statistics():
    """
    Get event system statistics.
    """
    try:
        event_bus = get_event_bus()
        
        stats = {
            'event_queue_size': len(event_bus._event_queue),
            'registered_handlers': len(event_bus._handlers.get('state_change', [])),
            'event_processing_active': event_bus._running,
            'recent_events': list(event_bus._event_queue[-10:]) if event_bus._event_queue else []
        }
        
        return jsonify({
            'status': 'success',
            'event_statistics': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting event statistics: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to get event statistics: {str(e)}'
        }), 500


def _generate_recommendations(cache_stats: dict, event_stats: dict) -> list:
    """
    Generate recommendations based on current metrics.
    """
    recommendations = []
    
    # Cache utilization recommendations
    utilization = cache_stats.get('utilization_percent', 0)
    if utilization > 90:
        recommendations.append({
            'type': 'cache_size',
            'message': 'Cache utilization is high (>90%). Consider increasing cache_max_size.',
            'severity': 'warning'
        })
    elif utilization < 10:
        recommendations.append({
            'type': 'cache_efficiency',
            'message': 'Cache utilization is low (<10%). Consider reducing cache_max_size to save memory.',
            'severity': 'info'
        })
    
    # Event queue recommendations
    queue_size = event_stats.get('event_queue_size', 0)
    if queue_size > 100:
        recommendations.append({
            'type': 'event_processing',
            'message': f'Event queue is large ({queue_size} events). Check event processing performance.',
            'severity': 'warning'
        })
    
    # Handler recommendations
    handler_count = event_stats.get('registered_handlers', 0)
    if handler_count == 0:
        recommendations.append({
            'type': 'event_handlers',
            'message': 'No event handlers registered. Cache invalidation may not work properly.',
            'severity': 'error'
        })
    
    # State tracking recommendations
    tracked_ads = cache_stats.get('tracked_advertisements', 0)
    tracked_offers = cache_stats.get('tracked_buy_offers', 0)
    tracked_assets = cache_stats.get('tracked_assets', 0)
    
    if tracked_ads + tracked_offers + tracked_assets == 0:
        recommendations.append({
            'type': 'state_tracking',
            'message': 'No state dependencies tracked. Consider enabling state-aware caching.',
            'severity': 'info'
        })
    
    return recommendations


# Register the blueprint with the main app
def register_blueprint(app):
    """Register the validation metrics blueprint with the Flask app."""
    app.register_blueprint(validation_metrics_bp)
    logger.info("Registered state-aware validation metrics API endpoints")

