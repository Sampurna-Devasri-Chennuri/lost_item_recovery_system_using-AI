"""
Database models for the Items app.
Defines tables for items, AI match results, claims workflow, and notifications.
"""

from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class Item(models.Model):
    """
    Item model - Main model for Lost and Found items.
    """
    
    # Item status choices
    STATUS_CHOICES = [
        ('lost', 'Lost'),
        ('found', 'Found'),
    ]
    
    # Category choices
    CATEGORY_CHOICES = [
        ('electronics', 'Electronics'),           # Mobile, laptop, etc.
        ('documents', 'Documents & ID Cards'),    # ID cards, licenses, certificates
        ('accessories', 'Accessories'),           # Watches, jewelry, glasses
        ('clothing', 'Clothing'),                 # Apparel, jackets
        ('books', 'Books & Stationery'),          # Books, notebooks, calculators
        ('keys', 'Keys'),                         # Dorm, bike, car keys
        ('wallet', 'Wallet & Money'),             # Wallets, purses
        ('bags', 'Bags & Luggage'),               # Backpacks, luggage
        ('other', 'Other'),                       # Miscellaneous items
    ]
    
    # Basic item information fields
    title = models.CharField(
        max_length=200,
        help_text="Title or brief name of the item"
    )
    
    description = models.TextField(
        help_text="Detailed description of the item (color, brand, distinguishing marks, etc.)"
    )
    
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='other',
        help_text="Select item category"
    )
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='lost',
        help_text="Whether the item was lost or found"
    )
    
    # Image field
    image = models.ImageField(
        upload_to='item_images/',
        blank=True,
        null=True,
        help_text="Upload a photo of the item (optional but recommended)"
    )
    
    # Location and date
    location = models.CharField(
        max_length=255,
        help_text="Campus location where the item was lost or found"
    )
    
    date_lost_found = models.DateField(
        help_text="Date when the item was lost or found"
    )
    
    # Contact information
    contact_email = models.EmailField(
        help_text="Contact email address"
    )
    
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number (optional)"
    )
    
    # User relationship
    posted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="User who posted this item"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Admin verification status
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether an admin has verified this listing"
    )
    
    # Item resolution status
    is_resolved = models.BooleanField(
        default=False,
        help_text="Whether the item has been recovered or resolved"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Item'
        verbose_name_plural = 'Items'
    
    def __str__(self):
        return f"{self.get_status_display()}: {self.title}"
    
    def get_absolute_url(self):
        return reverse('item_detail', kwargs={'pk': self.pk})
    
    @property
    def status_badge_class(self):
        if self.status == 'lost':
            return 'bg-danger'
        return 'bg-success'
    
    @property
    def category_icon(self):
        """Returns Bootstrap icon class corresponding to the category."""
        icon_map = {
            'electronics': 'bi-laptop',
            'documents': 'bi-card-text',
            'accessories': 'bi-watch',
            'clothing': 'bi-person-badge',
            'books': 'bi-book',
            'keys': 'bi-key',
            'wallet': 'bi-wallet2',
            'bags': 'bi-backpack',
            'other': 'bi-box-seam',
        }
        return icon_map.get(self.category, 'bi-tag')


class MatchRecord(models.Model):
    """
    Stores AI-computed similarity between a lost item and a found item.
    Enables persistent caching, dashboard listing, and audit tracking.
    """
    lost_item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='lost_matches',
        limit_choices_to={'status': 'lost'}
    )
    found_item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='found_matches',
        limit_choices_to={'status': 'found'}
    )
    similarity_score = models.FloatField(
        help_text="Overall composite match score percentage (0-100)"
    )
    text_score = models.FloatField(
        default=0.0,
        help_text="Text similarity percentage"
    )
    category_score = models.FloatField(
        default=0.0,
        help_text="Category similarity score (0-100)"
    )
    location_score = models.FloatField(
        default=0.0,
        help_text="Location proximity score (0-100)"
    )
    image_score = models.FloatField(
        default=0.0,
        help_text="Image visual similarity score (0-100)"
    )
    explanation = models.TextField(
        blank=True,
        help_text="Human-readable explanation of why items matched"
    )
    is_reviewed = models.BooleanField(
        default=False,
        help_text="Whether user has viewed this match"
    )
    is_dismissed = models.BooleanField(
        default=False,
        help_text="Whether user dismissed this match as not relevant"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-similarity_score', '-created_at']
        unique_together = ('lost_item', 'found_item')
        verbose_name = 'Match Record'
        verbose_name_plural = 'Match Records'

    def __str__(self):
        return f"Match: {self.lost_item.title} <-> {self.found_item.title} ({self.similarity_score:.1f}%)"


class ClaimRequest(models.Model):
    """
    Tracks formal recovery claims filed by a user on a listed item.
    Manages review, approval, rejection, and final recovery confirmation.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved / Handover Confirmed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled by Claimant'),
    ]

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='claims_received',
        help_text="The item being claimed"
    )
    claimant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='claims_made',
        help_text="The user claiming ownership"
    )
    matched_item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='associated_claims',
        help_text="Optional counterpart item posted by claimant"
    )
    proof_details = models.TextField(
        help_text="Proof of ownership: serial numbers, distinguishing marks, wallpaper description, contents, or purchase invoice details"
    )
    contact_phone = models.CharField(
        max_length=25,
        blank=True,
        help_text="Phone number for coordinating physical handover"
    )
    contact_email = models.EmailField(
        help_text="Email address for notifications"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    owner_notes = models.TextField(
        blank=True,
        help_text="Notes/comments from the item poster upon reviewing claim"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Claim Request'
        verbose_name_plural = 'Claim Requests'

    def __str__(self):
        return f"Claim #{self.id} for '{self.item.title}' by {self.claimant.username} ({self.get_status_display()})"

    @property
    def status_badge_class(self):
        status_map = {
            'pending': 'bg-warning text-dark',
            'approved': 'bg-success',
            'rejected': 'bg-danger',
            'cancelled': 'bg-secondary',
        }
        return status_map.get(self.status, 'bg-secondary')


class Notification(models.Model):
    """
    In-app notification system for match discoveries, claim updates, and resolutions.
    """
    NOTIFICATION_TYPES = [
        ('match_found', 'Potential Match Found'),
        ('claim_received', 'New Claim Request'),
        ('claim_approved', 'Claim Approved'),
        ('claim_rejected', 'Claim Rejected'),
        ('item_resolved', 'Item Recovered'),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPES
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"

    @property
    def icon_class(self):
        icon_map = {
            'match_found': 'bi-cpu text-info',
            'claim_received': 'bi-file-earmark-person text-warning',
            'claim_approved': 'bi-check-circle text-success',
            'claim_rejected': 'bi-x-circle text-danger',
            'item_resolved': 'bi-patch-check text-primary',
        }
        return icon_map.get(self.notification_type, 'bi-bell text-secondary')
