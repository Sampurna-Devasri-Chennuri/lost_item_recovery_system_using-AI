"""
Admin configuration for Items app.
Configures administrative dashboard for Items, AI Matches, Claims, and Notifications.
"""

from django.contrib import admin
from .models import Item, MatchRecord, ClaimRequest, Notification


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'status',
        'category',
        'posted_by',
        'location',
        'date_lost_found',
        'is_verified',
        'is_resolved',
        'created_at',
    ]
    list_filter = [
        'status',
        'category',
        'is_verified',
        'is_resolved',
        'created_at',
    ]
    search_fields = [
        'title',
        'description',
        'location',
        'posted_by__username',
        'posted_by__email',
    ]
    list_editable = [
        'is_verified',
        'is_resolved',
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    actions = ['mark_verified', 'mark_unverified', 'mark_resolved']

    def mark_verified(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f'{count} items marked as verified.')
    mark_verified.short_description = 'Mark selected items as verified'

    def mark_unverified(self, request, queryset):
        count = queryset.update(is_verified=False)
        self.message_user(request, f'{count} items marked as unverified.')
    mark_unverified.short_description = 'Mark selected items as unverified'

    def mark_resolved(self, request, queryset):
        count = queryset.update(is_resolved=True)
        self.message_user(request, f'{count} items marked as resolved.')
    mark_resolved.short_description = 'Mark selected items as resolved'


@admin.register(MatchRecord)
class MatchRecordAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'lost_item',
        'found_item',
        'similarity_score',
        'text_score',
        'category_score',
        'location_score',
        'image_score',
        'is_reviewed',
        'is_dismissed',
        'created_at',
    ]
    list_filter = ['is_reviewed', 'is_dismissed', 'created_at']
    search_fields = ['lost_item__title', 'found_item__title', 'explanation']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ClaimRequest)
class ClaimRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'item',
        'claimant',
        'status',
        'contact_email',
        'contact_phone',
        'created_at',
        'resolved_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['item__title', 'claimant__username', 'proof_details', 'contact_email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'recipient',
        'notification_type',
        'title',
        'is_read',
        'created_at',
    ]
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'title', 'message']
    readonly_fields = ['created_at']
