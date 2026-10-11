"""
Views for the Items app.
Handles items CRUD, AI matching exploration, claim recovery workflows, and notifications.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import (
    ListView, 
    DetailView, 
    CreateView, 
    UpdateView, 
    DeleteView
)
from django.urls import reverse_lazy, reverse
from django.db.models import Q
from django.utils import timezone

from .models import Item, MatchRecord, ClaimRequest, Notification
from .forms import (
    ItemForm, 
    UserRegisterForm, 
    ItemSearchForm, 
    ClaimRequestForm, 
    ClaimReviewForm
)
from .ai_matching import (
    get_candidate_matches_for_item, 
    sync_item_matches, 
    compare_items
)


# ==================== Authentication Views ====================

def register_view(request):
    """
    User registration view.
    Creates new account, automatically signs in the user, and redirects to dashboard.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request, 
                f'Welcome {user.first_name or user.username}! Your account has been created successfully.'
            )
            return redirect('dashboard')
    else:
        form = UserRegisterForm()
    
    context = {
        'form': form,
        'title': 'Sign Up'
    }
    return render(request, 'registration/register.html', context)


# ==================== Item List & Search Views ====================

class ItemListView(ListView):
    """
    Public listing of all items with search and multi-criteria filtering.
    """
    model = Item
    template_name = 'items/item_list.html'
    context_object_name = 'items'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Item.objects.select_related('posted_by').all()
        
        # Include resolved items only if explicitly requested, otherwise show active
        show_resolved = self.request.GET.get('show_resolved', '0') == '1'
        if not show_resolved:
            queryset = queryset.filter(is_resolved=False)
        
        # Keyword search across title, description, location
        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(description__icontains=query) |
                Q(location__icontains=query)
            )
        
        # Category filter
        category = self.request.GET.get('category', '').strip()
        if category:
            queryset = queryset.filter(category=category)
        
        # Status filter (lost vs found)
        status = self.request.GET.get('status', '').strip()
        if status:
            queryset = queryset.filter(status=status)
            
        # Location filter
        location = self.request.GET.get('location', '').strip()
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ItemSearchForm(self.request.GET)
        context['total_lost'] = Item.objects.filter(status='lost', is_resolved=False).count()
        context['total_found'] = Item.objects.filter(status='found', is_resolved=False).count()
        context['total_resolved'] = Item.objects.filter(is_resolved=True).count()
        context['current_category'] = self.request.GET.get('category', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_query'] = self.request.GET.get('query', '')
        context['page_title'] = 'Campus Lost & Found Directory'
        return context


class LostItemListView(ItemListView):
    """
    Dedicated view for lost items.
    """
    def get_queryset(self):
        return super().get_queryset().filter(status='lost')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Lost Items Directory'
        context['status_filter'] = 'lost'
        return context


class FoundItemListView(ItemListView):
    """
    Dedicated view for found items.
    """
    def get_queryset(self):
        return super().get_queryset().filter(status='found')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Found Items Directory'
        context['status_filter'] = 'found'
        return context


# ==================== Item Detail View ====================

class ItemDetailView(DetailView):
    """
    Displays single item details along with AI-ranked matching candidates and claim status.
    """
    model = Item
    template_name = 'items/item_detail.html'
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.object
        user = self.request.user
        
        # Retrieve candidate matches using the hybrid AI matching engine
        context['matches'] = get_candidate_matches_for_item(item, min_score=15.0, top_n=6)
        context['match_type'] = 'found' if item.status == 'lost' else 'lost'
        
        is_owner = user.is_authenticated and (user == item.posted_by)
        context['is_owner'] = is_owner
        
        if user.is_authenticated:
            if not is_owner:
                # Check if current user has already filed a claim on this item
                existing_claim = ClaimRequest.objects.filter(
                    item=item,
                    claimant=user
                ).first()
                context['user_claim'] = existing_claim
                context['claim_form'] = ClaimRequestForm(user=user, target_item=item)
            else:
                # Poster sees claims received for this item
                context['claims_received'] = ClaimRequest.objects.filter(
                    item=item
                ).select_related('claimant').order_by('-created_at')
        
        return context


# ==================== Item CRUD Views ====================

class ItemCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new lost or found listing. Automatically triggers AI matching on save.
    """
    model = Item
    form_class = ItemForm
    template_name = 'items/item_form.html'
    
    def form_valid(self, form):
        form.instance.posted_by = self.request.user
        if not form.instance.contact_email:
            form.instance.contact_email = self.request.user.email
            
        response = super().form_valid(form)
        
        # Trigger AI matching synchronization
        try:
            synced = sync_item_matches(self.object, threshold=20.0)
            if synced:
                messages.info(
                    self.request,
                    f"AI Match Engine found {len(synced)} potential candidate match(es) for your item!"
                )
        except Exception as e:
            # Match failure should not disrupt item creation
            pass
            
        messages.success(self.request, 'Your item has been posted successfully!')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Report Item'
        context['button_text'] = 'Post Item'
        return context


class ItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Update item details. Only owner can update.
    """
    model = Item
    form_class = ItemForm
    template_name = 'items/item_form.html'
    
    def test_func(self):
        item = self.get_object()
        return self.request.user == item.posted_by
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Recalculate AI matches on item update
        try:
            sync_item_matches(self.object, threshold=20.0)
        except Exception:
            pass
        messages.success(self.request, 'Item updated successfully!')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Listing'
        context['button_text'] = 'Save Changes'
        return context


class ItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Delete item. Only owner can delete.
    """
    model = Item
    template_name = 'items/item_confirm_delete.html'
    success_url = reverse_lazy('my_items')
    
    def test_func(self):
        item = self.get_object()
        return self.request.user == item.posted_by
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Item listing deleted successfully.')
        return super().delete(request, *args, **kwargs)


# ==================== User Profile & My Items ====================

@login_required
def my_items_view(request):
    """
    User's reported items management page.
    """
    items = Item.objects.filter(posted_by=request.user)
    
    status = request.GET.get('status', '').strip()
    if status == 'lost':
        items = items.filter(status='lost', is_resolved=False)
    elif status == 'found':
        items = items.filter(status='found', is_resolved=False)
    elif status == 'resolved':
        items = items.filter(is_resolved=True)
    
    all_user_items = Item.objects.filter(posted_by=request.user)
    
    context = {
        'items': items,
        'title': 'My Reported Items',
        'total_items': all_user_items.count(),
        'lost_count': all_user_items.filter(status='lost', is_resolved=False).count(),
        'found_count': all_user_items.filter(status='found', is_resolved=False).count(),
        'resolved_count': all_user_items.filter(is_resolved=True).count(),
        'current_status': status,
    }
    return render(request, 'items/my_items.html', context)


@login_required
def mark_resolved_view(request, pk):
    """
    Marks an item as recovered / resolved.
    """
    item = get_object_or_404(Item, pk=pk)
    
    if request.user != item.posted_by and not request.user.is_staff:
        messages.error(request, 'You can only update recovery status for your own listings.')
        return redirect('item_detail', pk=pk)
    
    item.is_resolved = not item.is_resolved
    item.save()
    
    status_label = "resolved / recovered" if item.is_resolved else "reopened as active"
    messages.success(request, f"Item '{item.title}' marked as {status_label}!")
    
    # Notify claimants of approved claims that handover is confirmed
    if item.is_resolved:
        approved_claims = ClaimRequest.objects.filter(item=item, status='approved')
        for claim in approved_claims:
            claim.resolved_at = timezone.now()
            claim.save()
            Notification.objects.create(
                recipient=claim.claimant,
                notification_type='item_resolved',
                title=f"Item Recovered: {item.title}",
                message=f"The item '{item.title}' has been officially marked as resolved and recovered.",
                link=f"/items/{item.pk}/"
            )
            
    return redirect('my_items')


# ==================== AI Matches Hub ====================

def item_matches_view(request, pk):
    """
    Dedicated view to inspect full AI similarity breakdown for an item against potential matches.
    """
    item = get_object_or_404(Item, pk=pk)
    sync_item_matches(item, threshold=15.0)
    matches = get_candidate_matches_for_item(item, min_score=15.0, top_n=10)
    
    context = {
        'item': item,
        'matches': matches,
        'title': f"AI Matches for {item.title}",
    }
    return render(request, 'items/item_matches.html', context)


# ==================== Item Claim & Recovery Workflow ====================

@login_required
def submit_claim_view(request, pk):
    """
    Submit a formal recovery claim on an item.
    """
    item = get_object_or_404(Item, pk=pk)
    
    # Poster cannot claim their own item
    if request.user == item.posted_by:
        messages.error(request, "You cannot file a claim on an item you reported.")
        return redirect('item_detail', pk=pk)
    
    if item.is_resolved:
        messages.warning(request, "This item has already been marked as resolved.")
        return redirect('item_detail', pk=pk)
    
    if request.method == 'POST':
        form = ClaimRequestForm(request.POST, user=request.user, target_item=item)
        if form.is_valid():
            # Check for existing pending claim
            existing = ClaimRequest.objects.filter(
                item=item,
                claimant=request.user,
                status='pending'
            ).first()
            if existing:
                messages.warning(request, "You already have a pending claim for this item.")
                return redirect('claim_detail', pk=existing.pk)
            
            claim = form.save(commit=False)
            claim.item = item
            claim.claimant = request.user
            claim.save()
            
            # Create notification for item poster
            Notification.objects.create(
                recipient=item.posted_by,
                notification_type='claim_received',
                title=f"New Claim Request for '{item.title}'",
                message=f"{request.user.get_full_name() or request.user.username} has submitted a recovery claim for '{item.title}'. Please review their proof details.",
                link=f"/claims/{claim.pk}/"
            )
            
            messages.success(
                request,
                "Your claim has been submitted successfully! The poster has been notified to review your proof."
            )
            return redirect('claim_detail', pk=claim.pk)
    else:
        form = ClaimRequestForm(user=request.user, target_item=item)
    
    context = {
        'form': form,
        'item': item,
        'title': f"Submit Claim for {item.title}"
    }
    return render(request, 'items/claim_form.html', context)


@login_required
def claim_detail_view(request, pk):
    """
    View details and status of a specific recovery claim.
    """
    claim = get_object_or_404(
        ClaimRequest.objects.select_related('item', 'claimant', 'item__posted_by', 'matched_item'),
        pk=pk
    )
    
    # Only claimant, item poster, or admin can view
    if request.user != claim.claimant and request.user != claim.item.posted_by and not request.user.is_staff:
        messages.error(request, "You do not have permission to view this claim.")
        return redirect('dashboard')
    
    is_owner = (request.user == claim.item.posted_by)
    review_form = ClaimReviewForm(instance=claim) if is_owner else None
    
    context = {
        'claim': claim,
        'is_owner': is_owner,
        'review_form': review_form,
        'title': f"Claim #{claim.id} - {claim.item.title}"
    }
    return render(request, 'items/claim_detail.html', context)


@login_required
def review_claim_view(request, pk):
    """
    Item owner approves or rejects a recovery claim.
    """
    claim = get_object_or_404(
        ClaimRequest.objects.select_related('item', 'claimant', 'item__posted_by'),
        pk=pk
    )
    
    if request.user != claim.item.posted_by and not request.user.is_staff:
        messages.error(request, "Only the listing poster can review this claim.")
        return redirect('claim_detail', pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        owner_notes = request.POST.get('owner_notes', '').strip()
        mark_recovered = request.POST.get('mark_recovered', '') == '1'
        
        if action == 'approve':
            claim.status = 'approved'
            claim.owner_notes = owner_notes
            claim.resolved_at = timezone.now()
            claim.save()
            
            # Optionally mark item as resolved if handover is settled
            if mark_recovered:
                claim.item.is_resolved = True
                claim.item.save()
                
            Notification.objects.create(
                recipient=claim.claimant,
                notification_type='claim_approved',
                title=f"Claim Approved: {claim.item.title}",
                message=f"Congratulations! Your claim for '{claim.item.title}' was approved by the poster. Notes: {owner_notes or 'Please coordinate handover.'}",
                link=f"/claims/{claim.pk}/"
            )
            messages.success(request, f"Claim #{claim.id} has been approved! The claimant has been notified.")
            
        elif action == 'reject':
            claim.status = 'rejected'
            claim.owner_notes = owner_notes
            claim.save()
            
            Notification.objects.create(
                recipient=claim.claimant,
                notification_type='claim_rejected',
                title=f"Claim Rejected: {claim.item.title}",
                message=f"Your claim for '{claim.item.title}' was declined. Reason: {owner_notes or 'Proof could not be verified.'}",
                link=f"/claims/{claim.pk}/"
            )
            messages.warning(request, f"Claim #{claim.id} has been rejected.")
            
        return redirect('claim_detail', pk=claim.pk)
        
    return redirect('claim_detail', pk=pk)


@login_required
def my_claims_view(request):
    """
    Dashboard of all claims related to the current user:
    1. Incoming claims on user's posted items.
    2. Outgoing claims submitted by the user.
    """
    incoming_claims = ClaimRequest.objects.filter(
        item__posted_by=request.user
    ).select_related('item', 'claimant').order_by('-created_at')
    
    outgoing_claims = ClaimRequest.objects.filter(
        claimant=request.user
    ).select_related('item', 'item__posted_by').order_by('-created_at')
    
    context = {
        'incoming_claims': incoming_claims,
        'outgoing_claims': outgoing_claims,
        'title': 'Claims & Recovery Center'
    }
    return render(request, 'items/my_claims.html', context)


# ==================== Notifications ====================

@login_required
def notifications_list_view(request):
    """
    List all notifications for the current user.
    """
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')
    
    context = {
        'notifications': notifications,
        'title': 'Notifications'
    }
    return render(request, 'items/notifications.html', context)


@login_required
def mark_notification_read_view(request, pk):
    """
    Mark single notification as read and redirect to destination link.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    
    if notification.link:
        return redirect(notification.link)
    return redirect('notifications')


@login_required
def mark_all_notifications_read_view(request):
    """
    Mark all unread notifications as read.
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('notifications')


# ==================== Dashboard View ====================

def dashboard_view(request):
    """
    Main SaaS-style portal dashboard.
    Displays live real-time platform statistics, user-specific AI match alerts,
    active claims, and recent lost and found listings.
    """
    # Global metrics
    total_lost = Item.objects.filter(status='lost', is_resolved=False).count()
    total_found = Item.objects.filter(status='found', is_resolved=False).count()
    total_resolved = Item.objects.filter(is_resolved=True).count()
    total_items = Item.objects.count()
    
    # Recent items
    recent_lost = Item.objects.filter(status='lost', is_resolved=False).select_related('posted_by')[:6]
    recent_found = Item.objects.filter(status='found', is_resolved=False).select_related('posted_by')[:6]
    
    context = {
        'total_items': total_items,
        'total_lost': total_lost,
        'total_found': total_found,
        'total_resolved': total_resolved,
        'recent_lost': recent_lost,
        'recent_found': recent_found,
    }
    
    if request.user.is_authenticated:
        user = request.user
        user_items = Item.objects.filter(posted_by=user)
        user_item_ids = list(user_items.values_list('id', flat=True))
        
        # User match records
        user_matches = MatchRecord.objects.filter(
            Q(lost_item_id__in=user_item_ids) | Q(found_item_id__in=user_item_ids),
            is_dismissed=False
        ).select_related('lost_item', 'found_item').order_by('-similarity_score')[:5]
        
        # Claims
        pending_incoming = ClaimRequest.objects.filter(
            item__posted_by=user,
            status='pending'
        ).select_related('item', 'claimant')
        
        my_claims = ClaimRequest.objects.filter(
            claimant=user
        ).select_related('item').order_by('-created_at')[:5]
        
        # Notifications
        recent_notifications = Notification.objects.filter(
            recipient=user
        ).order_by('-created_at')[:5]
        
        context.update({
            'my_items_count': user_items.count(),
            'my_lost_count': user_items.filter(status='lost', is_resolved=False).count(),
            'my_found_count': user_items.filter(status='found', is_resolved=False).count(),
            'my_resolved_count': user_items.filter(is_resolved=True).count(),
            'user_matches': user_matches,
            'user_matches_count': MatchRecord.objects.filter(
                Q(lost_item_id__in=user_item_ids) | Q(found_item_id__in=user_item_ids),
                is_dismissed=False
            ).count(),
            'pending_incoming_claims': pending_incoming,
            'my_claims': my_claims,
            'recent_notifications': recent_notifications,
            'my_recent_items': user_items.order_by('-created_at')[:4],
        })
        
    return render(request, 'items/dashboard.html', context)
