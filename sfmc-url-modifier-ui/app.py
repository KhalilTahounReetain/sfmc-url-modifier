#!/usr/bin/env python3
"""
SFMC URL Modifier - Web UI
"""

import os
import sys
import re
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

# .env
env_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), '..', 'sfmc-url-modifier', '.env')
load_dotenv(env_path)

# Modules SFMC
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sfmc-welcome-url-modifier'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sfmc-url-modifier'))

from sfmc_auth import SFMCAuth
from sfmc_api import SFMCAPI
from config import extract_country_from_name, get_url_patterns_for_journey, COUNTRY_URL_MAPPINGS

app = Flask(__name__)

# Global API instance
api = None
auth = None


def get_api():
    global api, auth
    if api is None:
        auth = SFMCAuth()
        auth.refresh()
        api = SFMCAPI(auth)
    return api


def refresh_connection():
    global api, auth
    auth = SFMCAuth()
    auth.refresh()
    api = SFMCAPI(auth)
    return api


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/connect', methods=['POST'])
def connect():
    try:
        refresh_connection()
        return jsonify({'success': True, 'message': 'Connexion réussie'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/journeys', methods=['GET'])
def get_journeys():
    """GET /api/journeys?type=all&page=1&page_size=50&exclude_stopped=true&no_cache=false"""
    try:
        api = get_api()
        journey_type = request.args.get('type', 'all')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 50))
        exclude_stopped = request.args.get('exclude_stopped', 'true').lower() == 'true'
        no_cache = request.args.get('no_cache', 'false').lower() == 'true'

        if no_cache:
            api.invalidate_cache()

        data = api.get_journeys_paginated(
            page=page,
            page_size=page_size,
            journey_type=journey_type,
            exclude_stopped=exclude_stopped
        )

        result = []
        for j in data['items']:
            name = j.get('name', '')
            country = extract_country_from_name(name)
            patterns = get_url_patterns_for_journey(name)
            result.append({
                'id': j.get('id'),
                'name': name,
                'status': j.get('status'),
                'type': j.get('definitionType'),
                'modifiedDate': j.get('modifiedDate'),
                'country': country,
                'patterns': patterns
            })

        return jsonify({
            'success': True,
            'journeys': result,
            'count': len(result),
            'total': data['total'],
            'page': data['page'],
            'page_size': data['page_size'],
            'has_more': data['has_more'],
            'from_cache': data['from_cache']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        api = get_api()
        data = request.json
        journey_id = data.get('journey_id')
        asset_id = data.get('asset_id')
        auto_detect = data.get('auto_detect', True)
        old_pattern = data.get('old', 'fr')
        new_pattern = data.get('new', 'fr-fr')
        url_replacements = data.get('url_replacements', [])

        results = []

        if asset_id:
            r = api.process_email_asset(asset_id, old_pattern, new_pattern, dry_run=True, url_replacements=url_replacements)
            results.append(r)
        elif journey_id:
            activities, journey = api.get_journey_activities(journey_id)
            journey_name = journey.get('name', '')

            # Auto-détection du pays
            if auto_detect:
                patterns = get_url_patterns_for_journey(journey_name)
                if patterns:
                    old_pattern, new_pattern = patterns
                    country = extract_country_from_name(journey_name)
                else:
                    country = None
            else:
                country = None

            journey_info = {
                'name': journey_name,
                'status': journey.get('status'),
                'activities_count': len(activities),
                'country_detected': country,
                'old_pattern': old_pattern,
                'new_pattern': new_pattern
            }

            for act in activities:
                aid = extract_asset_id(act)
                if aid:
                    r = api.process_email_asset(aid, old_pattern, new_pattern, dry_run=True, url_replacements=url_replacements)
                    r['activity_name'] = act.get('name')
                    results.append(r)

            return jsonify({
                'success': True,
                'journey': journey_info,
                'results': results,
                'total_changes': sum(len(r.get('changes', [])) for r in results)
            })

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/execute', methods=['POST'])
def execute():
    try:
        api = get_api()
        data = request.json
        journey_id = data.get('journey_id')
        asset_id = data.get('asset_id')
        auto_detect = data.get('auto_detect', True)
        old_pattern = data.get('old', 'fr')
        new_pattern = data.get('new', 'fr-fr')
        refresh = data.get('refresh', False)
        url_replacements = data.get('url_replacements', [])

        results = []

        if asset_id:
            r = api.process_email_asset(asset_id, old_pattern, new_pattern, dry_run=False, url_replacements=url_replacements)
            results.append(r)
        elif journey_id:
            activities, journey = api.get_journey_activities(journey_id)
            journey_name = journey.get('name', '')

            # Auto-détection du pays
            if auto_detect:
                patterns = get_url_patterns_for_journey(journey_name)
                if patterns:
                    old_pattern, new_pattern = patterns
                    country = extract_country_from_name(journey_name)
                else:
                    country = None
            else:
                country = None

            for act in activities:
                aid = extract_asset_id(act)
                if aid:
                    r = api.process_email_asset(aid, old_pattern, new_pattern, dry_run=False, url_replacements=url_replacements)
                    r['activity_name'] = act.get('name')
                    results.append(r)

            total_changes = sum(len(r.get('changes', [])) for r in results)
            refresh_result = None
            if refresh and total_changes > 0:
                try:
                    refresh_result = api.refresh_journey(journey_id)
                except Exception as e:
                    refresh_result = {'error': str(e)}

            return jsonify({
                'success': True,
                'journey_name': journey_name,
                'country_detected': country,
                'old_pattern': old_pattern,
                'new_pattern': new_pattern,
                'results': results,
                'total_changes': total_changes,
                'refresh_result': refresh_result
            })

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/scan', methods=['POST'])
def scan():
    try:
        api = get_api()
        data = request.json
        journey_id = data.get('journey_id')
        auto_detect = data.get('auto_detect', True)
        old_pattern = data.get('old', 'fr')
        new_pattern = data.get('new', 'fr-fr')
        url_replacements = data.get('url_replacements', [])

        activities, journey = api.get_journey_activities(journey_id)
        journey_name = journey.get('name', '')

        # Auto-détection du pays
        if auto_detect:
            patterns = get_url_patterns_for_journey(journey_name)
            if patterns:
                old_pattern, new_pattern = patterns
                country = extract_country_from_name(journey_name)
            else:
                country = None
        else:
            country = None

        journey_info = {
            'name': journey_name,
            'status': journey.get('status'),
            'activities_count': len(activities),
            'country_detected': country,
            'old_pattern': old_pattern,
            'new_pattern': new_pattern
        }

        all_urls = []
        activity_results = []

        for act in activities:
            asset_id = extract_asset_id(act)
            if not asset_id:
                continue

            r = api.process_email_asset(asset_id, old_pattern, new_pattern, dry_run=True, url_replacements=url_replacements)

            urls = set()
            if r.get('changes'):
                for change in r['changes']:
                    context = change.get('context', '')
                    found = re.findall(r'https?://[^\s"\'<>]+', context)
                    for url in found:
                        clean = re.split(r'\?sez_client_id=|\?campaign=|&sez_', url)[0]
                        clean = clean.rstrip('?&')
                        # URLs de remplacement complet
                        if change.get('type') == 'full_url':
                            urls.add(change.get('original', ''))
                        elif f'/{old_pattern}' in clean and f'/{old_pattern}-' not in clean:
                            urls.add(clean)

            activity_results.append({
                'activity_name': act.get('name'),
                'asset_name': r.get('name'),
                'changes_count': len(r.get('changes', [])),
                'urls': sorted(list(urls))
            })
            all_urls.extend(urls)

        return jsonify({
            'success': True,
            'journey': journey_info,
            'activities': activity_results,
            'unique_urls': sorted(list(set(all_urls))),
            'total_urls': len(set(all_urls))
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/countries', methods=['GET'])
def get_countries():
    """Retourne les mappings pays supportés"""
    return jsonify({
        'success': True,
        'mappings': COUNTRY_URL_MAPPINGS
    })


@app.route('/api/refresh', methods=['POST'])
def refresh_journey():
    """Rafraîchit/Republie une journey"""
    try:
        api = get_api()
        data = request.json
        journey_id = data.get('journey_id')

        if not journey_id:
            return jsonify({'success': False, 'error': 'journey_id requis'})

        journey = api.get_journey_by_id(journey_id)
        journey_name = journey.get('name', '')
        status = journey.get('status', '')

        result = api.refresh_journey(journey_id)

        refresh_status = 'OK'
        if result is None:
            refresh_status = f'Status "{status}" - refresh manuel requis'

        return jsonify({
            'success': True,
            'journey_id': journey_id,
            'journey_name': journey_name,
            'journey_status': status,
            'refresh_status': refresh_status,
            'result': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/journey-emails', methods=['POST'])
def get_journey_emails():
    """Récupère la liste des emails d'une journey"""
    try:
        api = get_api()
        data = request.json
        journey_id = data.get('journey_id')

        if not journey_id:
            return jsonify({'success': False, 'error': 'journey_id requis'})

        activities, journey = api.get_journey_activities(journey_id)

        emails = []
        for act in activities:
            asset_id = extract_asset_id(act)
            if asset_id:
                try:
                    asset = api.get_asset_by_id(asset_id)
                    emails.append({
                        'asset_id': asset_id,
                        'activity_name': act.get('name'),
                        'name': asset.get('name'),
                        'type': act.get('type')
                    })
                except Exception:
                    emails.append({
                        'asset_id': asset_id,
                        'activity_name': act.get('name'),
                        'name': f'Asset {asset_id}',
                        'type': act.get('type')
                    })

        return jsonify({
            'success': True,
            'journey_id': journey_id,
            'journey_name': journey.get('name', ''),
            'emails': emails,
            'count': len(emails)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def extract_asset_id(activity):
    cfg = activity.get('config_args', {})

    if 'triggeredSend' in cfg:
        ts = cfg['triggeredSend']
        return ts.get('emailId') or ts.get('legacyEmailId') or ts.get('assetId')

    for k in ['emailId', 'assetId', 'legacyEmailId', 'contentBuilderAssetId']:
        if cfg.get(k):
            return cfg[k]
    return None


if __name__ == '__main__':
    app.run(debug=True, port=5001)
