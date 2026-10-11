"""
AI Matching Module for Campus Lost & Found System.
Combines TF-IDF vectorization, Cosine Similarity, categorical alignment,
location proximity, and visual color-distribution similarity.
Provides explainable match breakdowns and database persistence.
"""

import math
import numpy as np
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.db.models import Q


def extract_image_features(image_field):
    """
    Extracts a normalized color-distribution feature vector from an uploaded image.
    Uses PIL and numpy without requiring heavy external deep-learning weights.
    Returns a 96-dimensional normalized feature vector, or None if image cannot be read.
    """
    if not image_field:
        return None
    
    try:
        # Open image safely
        image_field.seek(0)
        with Image.open(image_field) as img:
            img = img.convert('RGB')
            img = img.resize((128, 128))
            arr = np.array(img, dtype=np.float32)

            # Compute normalized color histograms (32 bins per channel)
            r_hist, _ = np.histogram(arr[:, :, 0], bins=32, range=(0, 256), density=True)
            g_hist, _ = np.histogram(arr[:, :, 1], bins=32, range=(0, 256), density=True)
            b_hist, _ = np.histogram(arr[:, :, 2], bins=32, range=(0, 256), density=True)

            features = np.concatenate([r_hist, g_hist, b_hist])
            norm = np.linalg.norm(features)
            if norm > 0:
                features = features / norm
            return features
    except Exception as e:
        return None


def calculate_image_similarity(item1, item2):
    """
    Calculates visual similarity score (0.0 to 100.0) between two items' images.
    Returns (score, has_comparison) tuple.
    """
    feat1 = extract_image_features(item1.image)
    feat2 = extract_image_features(item2.image)

    if feat1 is None or feat2 is None:
        return 0.0, False

    sim = float(np.dot(feat1, feat2))
    # Clip between 0 and 1, convert to 0-100 percentage
    score = round(max(0.0, min(1.0, sim)) * 100, 2)
    return score, True


def calculate_text_similarity(text1, text2):
    """
    Calculates cosine similarity between two text snippets using TF-IDF.
    Handles short phrases, unigrams, and bigrams.
    """
    t1 = (text1 or '').strip().lower()
    t2 = (text2 or '').strip().lower()

    if not t1 or not t2:
        return 0.0

    # Quick exact match shortcut
    if t1 == t2:
        return 100.0

    try:
        vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),
            token_pattern=r'(?u)\b\w+\b',
            sublinear_tf=True
        )
        matrix = vectorizer.fit_transform([t1, t2])
        sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return round(float(sim) * 100, 2)
    except Exception:
        # Fallback to Jaccard token overlap
        words1 = set(t1.split())
        words2 = set(t2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return round((len(intersection) / len(union)) * 100, 2)


def calculate_category_score(cat1, cat2):
    """
    Calculates category alignment score (0.0 to 100.0).
    Soft matching allows related categories or 'other' to still match.
    """
    if not cat1 or not cat2:
        return 50.0

    if cat1 == cat2:
        return 100.0

    # Related category groups
    related_groups = [
        {'electronics', 'accessories'},
        {'wallet', 'bags', 'accessories'},
        {'books', 'documents'},
        {'clothing', 'accessories'},
    ]

    for group in related_groups:
        if cat1 in group and cat2 in group:
            return 65.0

    if cat1 == 'other' or cat2 == 'other':
        return 45.0

    return 20.0


def calculate_location_score(loc1, loc2):
    """
    Calculates location proximity score based on keyword overlap and substring matches.
    """
    l1 = (loc1 or '').strip().lower()
    l2 = (loc2 or '').strip().lower()

    if not l1 or not l2:
        return 40.0

    if l1 == l2:
        return 100.0

    if l1 in l2 or l2 in l1:
        return 85.0

    words1 = set(w for w in l1.replace(',', ' ').split() if len(w) > 2)
    words2 = set(w for w in l2.replace(',', ' ').split() if len(w) > 2)

    if not words1 or not words2:
        return 30.0

    overlap = words1.intersection(words2)
    if overlap:
        # Having shared anchor keywords (e.g. 'library', 'cafeteria', 'hostel') gives a strong baseline
        return round((len(overlap) / max(len(words1), len(words2))) * 65.0 + 35.0, 2)

    return 15.0


def compare_items(item1, item2):
    """
    Performs comprehensive hybrid comparison between two items.
    Returns a dictionary with composite score, component scores, and explanation.
    """
    # 1. Title Similarity
    title_score = calculate_text_similarity(item1.title, item2.title)

    # 2. Description Similarity
    desc_score = calculate_text_similarity(item1.description, item2.description)

    # Combined text score (Title 55%, Description 45%)
    combined_text = round((title_score * 0.55) + (desc_score * 0.45), 2)

    # 3. Category Score
    cat_score = calculate_category_score(item1.category, item2.category)

    # 4. Location Score
    loc_score = calculate_location_score(item1.location, item2.location)

    # 5. Image Score
    img_score, has_images = calculate_image_similarity(item1, item2)

    # Dynamic Weighting
    if has_images:
        # Title/Desc 60%, Category 15%, Location 15%, Image 10%
        composite = (
            (combined_text * 0.60) +
            (cat_score * 0.15) +
            (loc_score * 0.15) +
            (img_score * 0.10)
        )
    else:
        # Title/Desc 70%, Category 15%, Location 15%
        composite = (
            (combined_text * 0.70) +
            (cat_score * 0.15) +
            (loc_score * 0.15)
        )

    # Apply bonus if title is very high match
    if title_score >= 80.0 and cat_score >= 50.0:
        composite = min(100.0, composite + 5.0)

    composite = round(max(0.0, min(100.0, composite)), 1)

    # Generate explanatory remarks
    reasons = []
    if title_score >= 60:
        reasons.append(f"Strong title match: '{item1.title}' <-> '{item2.title}' ({title_score:.0f}%)")
    elif title_score >= 30:
        reasons.append(f"Partial title overlap ({title_score:.0f}%)")

    if cat_score == 100:
        reasons.append(f"Identical category: {item1.get_category_display()}")
    elif cat_score >= 50:
        reasons.append("Compatible category classification")

    if loc_score >= 70:
        reasons.append(f"Matching campus area: {item1.location} <-> {item2.location}")
    elif loc_score >= 40:
        reasons.append("Nearby campus area")

    if has_images:
        if img_score >= 65:
            reasons.append(f"Consistent visual color pattern ({img_score:.0f}%)")
        else:
            reasons.append("Visual color check completed")
    else:
        reasons.append("Text & metadata analysis (photos not compared)")

    explanation_str = " | ".join(reasons) if reasons else "General descriptive similarity"

    return {
        'similarity_score': composite,
        'text_score': combined_text,
        'title_score': title_score,
        'desc_score': desc_score,
        'category_score': cat_score,
        'location_score': loc_score,
        'image_score': img_score if has_images else 0.0,
        'has_image_comparison': has_images,
        'explanation': explanation_str,
    }


def sync_item_matches(item, threshold=20.0):
    """
    Synchronizes AI match records for an item in the database.
    Matches lost items against found items, or found items against lost items.
    Updates or creates MatchRecord instances and triggers user notifications.
    """
    from .models import Item, MatchRecord, Notification

    # Avoid matching resolved items
    if item.is_resolved:
        return []

    # Identify candidate target pool
    opposite_status = 'found' if item.status == 'lost' else 'lost'
    candidates = Item.objects.filter(
        status=opposite_status,
        is_resolved=False
    ).exclude(pk=item.pk)

    synced_records = []

    for candidate in candidates:
        match_data = compare_items(item, candidate)
        score = match_data['similarity_score']

        if score >= threshold:
            # Standardize lost vs found FK
            lost_item = item if item.status == 'lost' else candidate
            found_item = candidate if item.status == 'lost' else item

            record, created = MatchRecord.objects.update_or_create(
                lost_item=lost_item,
                found_item=found_item,
                defaults={
                    'similarity_score': score,
                    'text_score': match_data['text_score'],
                    'category_score': match_data['category_score'],
                    'location_score': match_data['location_score'],
                    'image_score': match_data['image_score'],
                    'explanation': match_data['explanation'],
                    'is_dismissed': False,
                }
            )
            synced_records.append(record)

            # Trigger notification if score is notable (>= 30%) and users are different
            if score >= 30.0 and lost_item.posted_by != found_item.posted_by:
                for target_user, counterpart in [
                    (lost_item.posted_by, found_item),
                    (found_item.posted_by, lost_item)
                ]:
                    title_text = f"Potential AI Match ({score:.0f}%): {counterpart.title}"
                    msg_text = (
                        f"An item matching your '{item.title}' was detected: "
                        f"'{counterpart.title}' ({counterpart.get_status_display()}) at {counterpart.location}. "
                        f"{match_data['explanation']}"
                    )
                    link_url = f"/items/{counterpart.pk}/"

                    # Avoid duplicate recent notifications
                    existing = Notification.objects.filter(
                        recipient=target_user,
                        link=link_url,
                        notification_type='match_found'
                    ).exists()

                    if not existing:
                        Notification.objects.create(
                            recipient=target_user,
                            notification_type='match_found',
                            title=title_text,
                            message=msg_text,
                            link=link_url
                        )

    return synced_records


def get_candidate_matches_for_item(item, min_score=15.0, top_n=6):
    """
    Returns ranked in-memory or persisted match results for an item.
    Always excludes self and items with the same status.
    """
    from .models import Item, MatchRecord

    # First check existing persisted MatchRecords
    if item.status == 'lost':
        db_records = MatchRecord.objects.filter(
            lost_item=item,
            found_item__is_resolved=False,
            is_dismissed=False,
            similarity_score__gte=min_score
        ).select_related('found_item', 'found_item__posted_by')[:top_n]

        if db_records.exists():
            return [
                {
                    'item': rec.found_item,
                    'similarity_score': rec.similarity_score,
                    'text_score': rec.text_score,
                    'category_score': rec.category_score,
                    'location_score': rec.location_score,
                    'image_score': rec.image_score,
                    'explanation': rec.explanation,
                    'match_record_id': rec.id,
                }
                for rec in db_records
            ]
    else:
        db_records = MatchRecord.objects.filter(
            found_item=item,
            lost_item__is_resolved=False,
            is_dismissed=False,
            similarity_score__gte=min_score
        ).select_related('lost_item', 'lost_item__posted_by')[:top_n]

        if db_records.exists():
            return [
                {
                    'item': rec.lost_item,
                    'similarity_score': rec.similarity_score,
                    'text_score': rec.text_score,
                    'category_score': rec.category_score,
                    'location_score': rec.location_score,
                    'image_score': rec.image_score,
                    'explanation': rec.explanation,
                    'match_record_id': rec.id,
                }
                for rec in db_records
            ]

    # If no records stored yet, compute on the fly and sync
    sync_item_matches(item, threshold=min_score)

    # Re-query
    if item.status == 'lost':
        return [
            {
                'item': rec.found_item,
                'similarity_score': rec.similarity_score,
                'text_score': rec.text_score,
                'category_score': rec.category_score,
                'location_score': rec.location_score,
                'image_score': rec.image_score,
                'explanation': rec.explanation,
                'match_record_id': rec.id,
            }
            for rec in MatchRecord.objects.filter(
                lost_item=item,
                found_item__is_resolved=False,
                is_dismissed=False,
                similarity_score__gte=min_score
            ).select_related('found_item', 'found_item__posted_by')[:top_n]
        ]
    else:
        return [
            {
                'item': rec.lost_item,
                'similarity_score': rec.similarity_score,
                'text_score': rec.text_score,
                'category_score': rec.category_score,
                'location_score': rec.location_score,
                'image_score': rec.image_score,
                'explanation': rec.explanation,
                'match_record_id': rec.id,
            }
            for rec in MatchRecord.objects.filter(
                found_item=item,
                lost_item__is_resolved=False,
                is_dismissed=False,
                similarity_score__gte=min_score
            ).select_related('lost_item', 'lost_item__posted_by')[:top_n]
        ]


# Backward-compatible helper functions
def find_matches_for_lost_item(lost_item, found_items_queryset=None, threshold=15, top_n=6):
    return get_candidate_matches_for_item(lost_item, min_score=threshold, top_n=top_n)


def find_matches_for_found_item(found_item, lost_items_queryset=None, threshold=15, top_n=6):
    return get_candidate_matches_for_item(found_item, min_score=threshold, top_n=top_n)
