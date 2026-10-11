"""
Context processors for the Items app.
Provides global notification counter and quick statistics to templates.
"""

from .models import Notification, ClaimRequest


def notification_context(request):
    """
    Supplies unread notification count and pending claims count to all templates.
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()

        pending_claims_count = ClaimRequest.objects.filter(
            item__posted_by=request.user,
            status='pending'
        ).count()

        return {
            'unread_notifications_count': unread_count,
            'pending_incoming_claims_count': pending_claims_count,
        }
    return {
        'unread_notifications_count': 0,
        'pending_incoming_claims_count': 0,
    }
