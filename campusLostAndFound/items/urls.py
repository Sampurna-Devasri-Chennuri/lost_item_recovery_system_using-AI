"""
URL configuration for Items app.
Routes views for item catalog, AI similarity hub, claim management, and notifications.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Main Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Item directory and search
    path('items/', views.ItemListView.as_view(), name='item_list'),
    path('items/lost/', views.LostItemListView.as_view(), name='lost_items'),
    path('items/found/', views.FoundItemListView.as_view(), name='found_items'),
    path('items/<int:pk>/', views.ItemDetailView.as_view(), name='item_detail'),
    
    # Item CRUD
    path('items/new/', views.ItemCreateView.as_view(), name='item_create'),
    path('items/<int:pk>/edit/', views.ItemUpdateView.as_view(), name='item_update'),
    path('items/<int:pk>/delete/', views.ItemDeleteView.as_view(), name='item_delete'),
    
    # AI Matches Hub
    path('items/<int:pk>/matches/', views.item_matches_view, name='item_matches'),
    
    # Claim and Recovery Workflow
    path('items/<int:pk>/claim/', views.submit_claim_view, name='submit_claim'),
    path('claims/<int:pk>/', views.claim_detail_view, name='claim_detail'),
    path('claims/<int:pk>/review/', views.review_claim_view, name='review_claim'),
    path('my-claims/', views.my_claims_view, name='my_claims'),
    
    # User inventory and resolution
    path('my-items/', views.my_items_view, name='my_items'),
    path('items/<int:pk>/resolve/', views.mark_resolved_view, name='mark_resolved'),
    
    # In-app Notifications
    path('notifications/', views.notifications_list_view, name='notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read_view, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read_view, name='mark_all_notifications_read'),
    
    # User Registration
    path('register/', views.register_view, name='register'),
]
