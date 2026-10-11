"""
Unit and Integration Tests for Campus Lost & Found System.
Tests authentication, item CRUD, AI matching engine, claim recovery workflow, and notifications.
"""

from datetime import date
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from items.models import Item, MatchRecord, ClaimRequest, Notification
from items.ai_matching import (
    calculate_text_similarity,
    calculate_category_score,
    calculate_location_score,
    compare_items,
    sync_item_matches,
    get_candidate_matches_for_item
)


class AuthenticationAndPermissionsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='student1',
            email='student1@campus.edu',
            password='Password123!',
            first_name='Student',
            last_name='One'
        )
        self.user2 = User.objects.create_user(
            username='student2',
            email='student2@campus.edu',
            password='Password123!',
            first_name='Student',
            last_name='Two'
        )

    def test_user_login(self):
        login_success = self.client.login(username='student1', password='Password123!')
        self.assertTrue(login_success)

    def test_registration_view(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@campus.edu',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_item_ownership_permissions(self):
        # user1 creates item
        item = Item.objects.create(
            title='Blue Dell Laptop',
            description='15 inch blue laptop with sticker',
            category='electronics',
            status='lost',
            location='Library 2nd Floor',
            date_lost_found=date.today(),
            contact_email='student1@campus.edu',
            posted_by=self.user1
        )

        # user2 logs in and tries to edit user1's item
        self.client.login(username='student2', password='Password123!')
        response = self.client.get(reverse('item_update', kwargs={'pk': item.pk}))
        # UserPassesTestMixin gives 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # user1 logs in and can access edit
        self.client.login(username='student1', password='Password123!')
        response = self.client.get(reverse('item_update', kwargs={'pk': item.pk}))
        self.assertEqual(response.status_code, 200)


class AIMatchingEngineTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='u1', email='u1@test.com', password='pass')
        self.user2 = User.objects.create_user(username='u2', email='u2@test.com', password='pass')

        self.lost_phone = Item.objects.create(
            title='iPhone 15 Pro Blue Titanium',
            description='Lost blue Apple iPhone 15 Pro with black leather case',
            category='electronics',
            status='lost',
            location='Main Campus Library',
            date_lost_found=date.today(),
            contact_email='u1@test.com',
            posted_by=self.user1
        )

        self.found_phone = Item.objects.create(
            title='iPhone 15 Pro Blue',
            description='Found blue iPhone 15 Pro in leather case near library counter',
            category='electronics',
            status='found',
            location='Library Ground Floor',
            date_lost_found=date.today(),
            contact_email='u2@test.com',
            posted_by=self.user2
        )

        self.found_keys = Item.objects.create(
            title='Honda Bike Key with Keychain',
            description='Found silver bike keys near parking lot',
            category='keys',
            status='found',
            location='North Parking',
            date_lost_found=date.today(),
            contact_email='u2@test.com',
            posted_by=self.user2
        )

    def test_text_similarity(self):
        sim = calculate_text_similarity("iPhone 15 Pro Blue", "iPhone 15 Pro Blue")
        self.assertEqual(sim, 100.0)

        sim_partial = calculate_text_similarity("iPhone 15 Pro", "iPhone 15 Pro Blue Leather")
        self.assertGreater(sim_partial, 40.0)

        sim_none = calculate_text_similarity("Gold Ring", "Scientific Calculator")
        self.assertEqual(sim_none, 0.0)

    def test_category_score(self):
        # Exact match
        self.assertEqual(calculate_category_score('electronics', 'electronics'), 100.0)
        # Related match (electronics & accessories)
        self.assertEqual(calculate_category_score('electronics', 'accessories'), 65.0)
        # Different
        self.assertEqual(calculate_category_score('clothing', 'electronics'), 20.0)

    def test_location_score(self):
        # Exact match
        self.assertEqual(calculate_location_score('Library', 'Library'), 100.0)
        # Substring / overlap
        score = calculate_location_score('Main Campus Library', 'Library Ground Floor')
        self.assertGreater(score, 50.0)

    def test_compare_items_score_high_for_matching_phone(self):
        res = compare_items(self.lost_phone, self.found_phone)
        self.assertGreaterEqual(res['similarity_score'], 60.0)
        self.assertIn('title', res['explanation'].lower())

    def test_compare_items_score_low_for_unrelated(self):
        res = compare_items(self.lost_phone, self.found_keys)
        self.assertLess(res['similarity_score'], 35.0)

    def test_sync_item_matches_creates_records_and_notifications(self):
        synced = sync_item_matches(self.lost_phone, threshold=25.0)
        self.assertGreaterEqual(len(synced), 1)

        match_record = MatchRecord.objects.filter(
            lost_item=self.lost_phone,
            found_item=self.found_phone
        ).first()
        self.assertIsNotNone(match_record)
        self.assertGreater(match_record.similarity_score, 50.0)

        # Verify notification created for both users
        u1_notifs = Notification.objects.filter(recipient=self.user1)
        u2_notifs = Notification.objects.filter(recipient=self.user2)
        self.assertTrue(u1_notifs.exists())
        self.assertTrue(u2_notifs.exists())


class ClaimAndRecoveryWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.finder = User.objects.create_user(username='finder', email='finder@campus.edu', password='Password123!')
        self.owner = User.objects.create_user(username='owner', email='owner@campus.edu', password='Password123!')

        self.found_item = Item.objects.create(
            title='Black Leather Wallet',
            description='Found black Tommy Hilfiger wallet with cash and cards',
            category='wallet',
            status='found',
            location='Student Cafeteria',
            date_lost_found=date.today(),
            contact_email='finder@campus.edu',
            posted_by=self.finder
        )

    def test_submit_claim_workflow(self):
        self.client.login(username='owner', password='Password123!')

        # Submit claim
        response = self.client.post(reverse('submit_claim', kwargs={'pk': self.found_item.pk}), {
            'proof_details': 'Wallet contains driving license for John Doe and 500 currency note.',
            'contact_phone': '+91 9988776655',
            'contact_email': 'owner@campus.edu'
        })
        self.assertEqual(response.status_code, 302)

        claim = ClaimRequest.objects.filter(item=self.found_item, claimant=self.owner).first()
        self.assertIsNotNone(claim)
        self.assertEqual(claim.status, 'pending')

        # Check finder got notification
        finder_notif = Notification.objects.filter(recipient=self.finder, notification_type='claim_received').first()
        self.assertIsNotNone(finder_notif)

    def test_prevent_owner_from_claiming_own_item(self):
        self.client.login(username='finder', password='Password123!')
        response = self.client.post(reverse('submit_claim', kwargs={'pk': self.found_item.pk}), {
            'proof_details': 'Self claim attempt',
            'contact_email': 'finder@campus.edu'
        })
        self.assertEqual(response.status_code, 302)
        # Ensure no claim created
        self.assertFalse(ClaimRequest.objects.filter(item=self.found_item, claimant=self.finder).exists())

    def test_approve_claim_and_mark_recovered(self):
        claim = ClaimRequest.objects.create(
            item=self.found_item,
            claimant=self.owner,
            proof_details='Contains ID card #12345',
            contact_email='owner@campus.edu',
            status='pending'
        )

        self.client.login(username='finder', password='Password123!')
        response = self.client.post(reverse('review_claim', kwargs={'pk': claim.pk}), {
            'action': 'approve',
            'owner_notes': 'Verified ID card. Meet at cafeteria.',
            'mark_recovered': '1'
        })
        self.assertEqual(response.status_code, 302)

        claim.refresh_from_db()
        self.assertEqual(claim.status, 'approved')

        self.found_item.refresh_from_db()
        self.assertTrue(self.found_item.is_resolved)

        # Check claimant received approval notification
        approval_notif = Notification.objects.filter(recipient=self.owner, notification_type='claim_approved').first()
        self.assertIsNotNone(approval_notif)


class ViewsAndDashboardTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='teststudent', email='test@campus.edu', password='Password123!')
        self.item = Item.objects.create(
            title='Scientific Calculator FX-991EX',
            description='Casio scientific calculator left in Lab 301',
            category='electronics',
            status='lost',
            location='Science Block Lab 301',
            date_lost_found=date.today(),
            contact_email='test@campus.edu',
            posted_by=self.user
        )

    def test_dashboard_view_anonymous(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Campus')
        self.assertContains(response, 'Active Lost Items')

    def test_dashboard_view_authenticated(self):
        self.client.login(username='teststudent', password='Password123!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activity Dashboard')

    def test_item_list_view_and_filtering(self):
        response = self.client.get(reverse('item_list'), {'query': 'Calculator'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Scientific Calculator')

        response_empty = self.client.get(reverse('item_list'), {'query': 'NonexistentTerm999'})
        self.assertEqual(response_empty.status_code, 200)
        self.assertContains(response_empty, 'No Matching Items Found')

    def test_item_detail_view(self):
        response = self.client.get(reverse('item_detail', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Scientific Calculator FX-991EX')

    def test_item_matches_view(self):
        response = self.client.get(reverse('item_matches', kwargs={'pk': self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AI Match Hub')
