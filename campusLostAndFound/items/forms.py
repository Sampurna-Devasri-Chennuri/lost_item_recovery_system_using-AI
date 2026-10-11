"""
Forms for the Items app.
Handles item listings, search, user registration, claims, and claim reviews.
"""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import Item, ClaimRequest


class UserRegisterForm(UserCreationForm):
    """
    User registration form extending Django's UserCreationForm.
    """
    email = forms.EmailField(
        required=True,
        help_text="Enter a valid university/personal email address"
    )
    first_name = forms.CharField(
        max_length=50,
        required=True,
        help_text="Your given name"
    )
    last_name = forms.CharField(
        max_length=50,
        required=True,
        help_text="Your family/surname"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['placeholder'] = field.label

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email address is already registered.")
        return email


class ItemForm(forms.ModelForm):
    """
    Item creation and update form with client and server validation.
    """
    date_lost_found = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Date when item was lost or found"
    )

    class Meta:
        model = Item
        fields = [
            'title',
            'description',
            'category',
            'status',
            'image',
            'location',
            'date_lost_found',
            'contact_email',
            'contact_phone',
        ]
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Provide detailed features, distinguishing marks, brand, color, or contents...'
            }),
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Blue Dell Laptop 15-inch, Black Titan Watch'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. Central Library 2nd Floor, Main Cafeteria'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': 'e.g. +91 9876543210'}),
            'contact_email': forms.EmailInput(attrs={'placeholder': 'e.g. student@campus.edu'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'image':
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (max 5 MB)
            if hasattr(image, 'size') and image.size > 5 * 1024 * 1024:
                raise ValidationError("Image file size must not exceed 5MB.")
        return image


class ItemSearchForm(forms.Form):
    """
    Form for search query and multi-parameter filtering.
    """
    query = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by keyword, title, location, description...'
        })
    )
    category = forms.ChoiceField(
        required=False,
        choices=[('', 'All Categories')] + Item.CATEGORY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + Item.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    location = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by campus location...'
        })
    )


class ClaimRequestForm(forms.ModelForm):
    """
    Form for claimants to file a recovery claim on a reported item.
    """
    class Meta:
        model = ClaimRequest
        fields = [
            'proof_details',
            'contact_phone',
            'contact_email',
            'matched_item',
        ]
        widgets = {
            'proof_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe unique identifiers, screen wallpapers, serial numbers, hidden marks, or contents that prove this is your item...'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number for meetup verification'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your active contact email'
            }),
            'matched_item': forms.Select(attrs={
                'class': 'form-select'
            })
        }

    def __init__(self, *args, user=None, target_item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proof_details'].required = True
        self.fields['contact_email'].required = True

        # Restrict matched_item to items posted by the current user
        if user and user.is_authenticated:
            opposite = 'lost' if target_item and target_item.status == 'found' else 'found'
            user_items = Item.objects.filter(posted_by=user, status=opposite, is_resolved=False)
            self.fields['matched_item'].queryset = user_items
            self.fields['matched_item'].required = False
            self.fields['matched_item'].empty_label = "(Optional) Select one of your reported items"
        else:
            self.fields['matched_item'].widget = forms.HiddenInput()


class ClaimReviewForm(forms.ModelForm):
    """
    Form for the item poster to accept or reject a filed claim.
    """
    class Meta:
        model = ClaimRequest
        fields = ['status', 'owner_notes']
        widgets = {
            'status': forms.Select(
                choices=[
                    ('approved', 'Approve Claim (Owner Verified & Ready for Handover)'),
                    ('rejected', 'Reject Claim (Proof Insufficient or Incorrect)'),
                ],
                attrs={'class': 'form-select'}
            ),
            'owner_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add instructions for meetup location, time, or reason for rejection...'
            })
        }
