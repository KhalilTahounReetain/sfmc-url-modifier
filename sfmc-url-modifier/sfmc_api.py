"""
SFMC API - Gestion journeys et emails
"""

import requests
import re
import time
from config import REST_BASE_URL


class JourneyCache:
    """Cache mémoire avec TTL"""
    def __init__(self, ttl_seconds=300):
        self.ttl = ttl_seconds
        self._cache = {}
        self._timestamps = {}

    def get(self, key):
        if key in self._cache:
            if time.time() - self._timestamps[key] < self.ttl:
                return self._cache[key]
            else:
                # Expired
                del self._cache[key]
                del self._timestamps[key]
        return None

    def set(self, key, value):
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def clear(self):
        self._cache.clear()
        self._timestamps.clear()

    def is_valid(self, key):
        return key in self._cache and (time.time() - self._timestamps[key] < self.ttl)


# Global cache instance
_journey_cache = JourneyCache(ttl_seconds=300)


class SFMCAPI:
    def __init__(self, auth):
        self.auth = auth
        self.base_url = REST_BASE_URL
        self.cache = _journey_cache

    # =====================
    # JOURNEYS
    # =====================

    def get_journeys(self, page_size=200, status_filter=None):
        url = f"{self.base_url}/interaction/v1/interactions"
        params = {
            "$pageSize": page_size,
            "$orderBy": "modifiedDate desc"
        }
        if status_filter:
            params["status"] = status_filter

        response = requests.get(url, headers=self.auth.get_headers(), params=params)
        response.raise_for_status()
        return response.json()

    def get_all_journeys(self, exclude_stopped=True, use_cache=True):
        """Récupère toutes les journeys avec pagination"""
        cache_key = f"all_journeys_exclude_{exclude_stopped}"

        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                print(f"  [CACHE HIT] Returning {len(cached)} cached journeys")
                return {'items': cached, 'count': len(cached), 'from_cache': True}

        all_items = []
        page = 1
        page_size = 200

        while True:
            url = f"{self.base_url}/interaction/v1/interactions"
            params = {
                "$pageSize": page_size,
                "$page": page,
                "$orderBy": "modifiedDate desc"
            }
            response = requests.get(url, headers=self.auth.get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            items = data.get('items', [])
            if exclude_stopped:
                items = [j for j in items if j.get('status') != 'Stopped']
            all_items.extend(items)

            if len(data.get('items', [])) < page_size:
                break
            page += 1

        self.cache.set(cache_key, all_items)

        return {'items': all_items, 'count': len(all_items), 'from_cache': False}

    def get_journeys_paginated(self, page=1, page_size=50, journey_type='all', exclude_stopped=True):
        """Pagination pour l'UI"""
        data = self.get_all_journeys(exclude_stopped=exclude_stopped, use_cache=True)
        all_journeys = data.get('items', [])

        if journey_type == 'transactional':
            filtered = [j for j in all_journeys if j.get('definitionType') == 'Transactional']
        elif journey_type == 'welcome':
            filtered = [j for j in all_journeys if 'welcome' in j.get('name', '').lower()]
        else:
            filtered = all_journeys

        total = len(filtered)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = filtered[start_idx:end_idx]

        has_more = end_idx < total

        return {
            'items': page_items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_more': has_more,
            'from_cache': data.get('from_cache', False)
        }

    def invalidate_cache(self):
        self.cache.clear()
        print("  [CACHE] Cleared")

    def get_journey_by_id(self, journey_id):
        url = f"{self.base_url}/interaction/v1/interactions/{journey_id}"
        response = requests.get(url, headers=self.auth.get_headers())
        response.raise_for_status()
        return response.json()

    def get_journey_activities(self, journey_id):
        journey = self.get_journey_by_id(journey_id)
        email_activities = []

        for activity in journey.get('activities', []):
            if activity.get('type') in ['EMAILV2', 'EMAIL', 'EMAILSEND']:
                email_activities.append({
                    'activity_id': activity.get('id'),
                    'activity_key': activity.get('key'),
                    'name': activity.get('name'),
                    'config_args': activity.get('configurationArguments', {}),
                    'type': activity.get('type')
                })

        return email_activities, journey

    def update_journey(self, journey_id, journey_data):
        url = f"{self.base_url}/interaction/v1/interactions/{journey_id}"
        response = requests.put(url, headers=self.auth.get_headers(), json=journey_data)
        response.raise_for_status()
        return response.json()

    def create_journey_version(self, journey_id):
        url = f"{self.base_url}/interaction/v1/interactions/{journey_id}/newVersion"
        response = requests.post(url, headers=self.auth.get_headers())
        response.raise_for_status()
        return response.json()

    def publish_journey(self, journey_id):
        url = f"{self.base_url}/interaction/v1/interactions/publishAsync/{journey_id}?versionNumber=1"
        response = requests.post(url, headers=self.auth.get_headers())
        response.raise_for_status()
        return response.json()

    def refresh_journey(self, journey_id):
        """Rafraîchit une journey pour appliquer les modifs emails"""
        journey = self.get_journey_by_id(journey_id)
        status = journey.get('status', '')
        print(f"  [INFO] Status: {status}")

        if status == 'Draft':
            print(f"  [INFO] Re-sauvegarde journey Draft...")
            result = self.update_journey(journey_id, journey)
            print(f"  [OK] Sauvegardé")
            return result

        elif status in ['Running', 'Published', 'Scheduled']:
            print(f"  [INFO] Création nouvelle version...")
            try:
                new_version = self.create_journey_version(journey_id)
                new_id = new_version.get('id', journey_id)
                print(f"  [OK] Version créée: {new_id}")
                print(f"  [INFO] Publication...")
                self.publish_journey(new_id)
                print(f"  [OK] Publié")
                return new_version
            except Exception as e:
                print(f"  [ERREUR] {e}")
                print(f"  [INFO] Faire manuellement dans Journey Builder")
                return None
        else:
            print(f"  [ATTENTION] Status '{status}' - refresh manuel requis")
            return None

    # =====================
    # ASSETS / EMAILS
    # =====================

    def get_asset_by_id(self, asset_id, try_legacy=True):
        url = f"{self.base_url}/asset/v1/content/assets/{asset_id}"
        try:
            response = requests.get(url, headers=self.auth.get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404 and try_legacy:
                print(f"  [INFO] Recherche par legacy ID...")
                legacy = self.get_email_by_legacy_id(asset_id)
                if legacy:
                    print(f"  [OK] Trouvé: {legacy.get('name')}")
                    return legacy
            raise

    def update_asset(self, asset_id, data):
        url = f"{self.base_url}/asset/v1/content/assets/{asset_id}"
        response = requests.patch(url, headers=self.auth.get_headers(), json=data)
        response.raise_for_status()
        return response.json()

    def get_email_by_legacy_id(self, email_id):
        url = f"{self.base_url}/asset/v1/content/assets"

        # Filtre simple
        try:
            params = {"$filter": f"legacyData.legacyId eq {email_id}"}
            response = requests.get(url, headers=self.auth.get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            if data.get('count', 0) > 0:
                return data['items'][0]
        except:
            pass

        # Query sur types email
        for email_type in ['htmlemail', 'templatebasedemail', 'textonlyemail']:
            try:
                query = {
                    "page": {"page": 1, "pageSize": 50},
                    "query": {
                        "leftOperand": {"property": "assetType.name", "simpleOperator": "equal", "value": email_type},
                        "logicalOperator": "AND",
                        "rightOperand": {"property": "data.email.legacy.legacyId", "simpleOperator": "equal", "value": str(email_id)}
                    }
                }
                response = requests.post(f"{url}/query", headers=self.auth.get_headers(), json=query)
                response.raise_for_status()
                data = response.json()
                if data.get('count', 0) > 0:
                    return data['items'][0]
            except:
                continue
        return None

    def search_assets(self, name_filter=None, asset_type="htmlemail"):
        url = f"{self.base_url}/asset/v1/content/assets"
        query = {
            "page": {"page": 1, "pageSize": 50},
            "query": {
                "leftOperand": {"property": "assetType.name", "simpleOperator": "equal", "value": asset_type},
                "logicalOperator": "AND",
                "rightOperand": {"property": "name", "simpleOperator": "like", "value": f"%{name_filter}%" if name_filter else "%"}
            }
        }
        response = requests.post(f"{url}/query", headers=self.auth.get_headers(), json=query)
        response.raise_for_status()
        return response.json()

    # =====================
    # URL REPLACEMENT
    # =====================

    def replace_urls_in_content(self, content, old_pattern, new_pattern, dry_run=True):
        """
        Remplace URLs dans HTML et AMPscript.
        Gère: /fr/, /fr", /fr', /fr<, /fr[space], /fr)
        Ne touche pas /fr-fr/
        """
        if not content:
            return content, []

        changes = []
        new_content = content

        # Patterns de remplacement
        patterns = [
            (rf'/{re.escape(old_pattern)}/(?!-)', f'/{new_pattern}/'),
            (rf'/{re.escape(old_pattern)}"', f'/{new_pattern}"'),
            (rf"/{re.escape(old_pattern)}'", f"/{new_pattern}'"),
            (rf'/{re.escape(old_pattern)}<', f'/{new_pattern}<'),
            (rf'/{re.escape(old_pattern)}(\s)', f'/{new_pattern}\\1'),
            (rf'/{re.escape(old_pattern)}\)', f'/{new_pattern})'),
        ]

        for pattern, replacement in patterns:
            for match in re.finditer(pattern, content):
                # Skip si déjà fr-fr
                prefix = content[max(0, match.start()-3):match.start()]
                if f'-{old_pattern}' in prefix:
                    continue
                changes.append({
                    'original': match.group(),
                    'position': match.start(),
                    'context': content[max(0, match.start()-30):match.end()+30]
                })

            if not dry_run:
                new_content = re.sub(pattern, replacement, new_content)

        return new_content, changes

    def process_email_asset(self, asset_id, old_pattern, new_pattern, dry_run=True):
        """Traite un email: récupère, modifie, sauvegarde"""
        result = {'asset_id': asset_id, 'name': None, 'changes': [], 'success': False, 'error': None}

        try:
            asset = self.get_asset_by_id(asset_id)
            result['name'] = asset.get('name')
            result['actual_asset_id'] = asset.get('id')

            # Trouver le contenu HTML
            html_content = None
            location = None

            if 'views' in asset and 'html' in asset['views']:
                html_content = asset['views']['html'].get('content', '')
                location = 'views.html.content'

            if not html_content and 'content' in asset:
                html_content = asset.get('content', '')
                location = 'content'

            if not html_content and 'data' in asset:
                html_content = asset.get('data', {}).get('email', {}).get('htmlBody', '')
                if html_content:
                    location = 'data.email.htmlBody'

            if not html_content:
                result['error'] = "HTML non trouvé"
                return result

            # Remplacer
            new_content, changes = self.replace_urls_in_content(html_content, old_pattern, new_pattern, dry_run)
            result['changes'] = changes
            result['changes_count'] = len(changes)

            if not dry_run and changes:
                # Sauvegarder
                if location == 'views.html.content':
                    update = {'views': {'html': {'content': new_content}}}
                elif location == 'data.email.htmlBody':
                    update = {'data': {'email': {'htmlBody': new_content}}}
                else:
                    update = {'content': new_content}

                self.update_asset(result['actual_asset_id'], update)
                result['success'] = True
                print(f"  [OK] {result['actual_asset_id']} - {len(changes)} modifs")
            else:
                result['success'] = True
                if dry_run:
                    print(f"  [DRY-RUN] {asset_id} - {len(changes)} modifs")

            return result

        except Exception as e:
            result['error'] = str(e)
            print(f"  [ERREUR] {asset_id}: {e}")
            return result
