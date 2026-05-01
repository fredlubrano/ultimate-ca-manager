"""
Pagination Helper
Simple pagination for SQLAlchemy queries
"""

import math


def paginate(query, page=1, per_page=20):
    """
    Paginate SQLAlchemy query
    
    Args:
        query: SQLAlchemy query object
        page: Page number (1-indexed)
        per_page: Items per page
    
    Returns:
        dict: {items, meta}
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    if per_page > 100:
        per_page = 100
    
    total = query.count()
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        'items': items,
        'meta': {
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    }


def parse_request_pagination(request, default_per_page=20):
    """
    Parse pagination parameters from Flask request args.

    Returns:
        tuple: (page, per_page) with defaults and bounds applied
    """
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(max(1, request.args.get('per_page', default_per_page, type=int)), 100)
    return page, per_page
