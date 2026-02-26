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
            result.append({
                'id': j.get('id'),
                'name': j.get('name'),
                'status': j.get('status'),
                'type': j.get('definitionType'),
                'modifiedDate': j.get('modifiedDate')
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
        old_pattern = data.get('old', 'fr')
        new_pattern = data.get('new', 'fr-fr')

        results = []

        if asset_id:
            r = api.process_email_asset(asset_id, old_pattern, new_pattern, dry_run=True)
            results.append(r)
        elif journey_id:
            activities, journey = api.get_journey_activities(journey_id)
            journey_info = {
                'name': journey.get('name'),
                'status': journey.get('status'),
                'activities_count': len(activities)
            }

            for act in activities:
                asset_id = extract_asset_id(act)
                if asset_id:
                    r = api.process_email_asset(asset_id, old_pattern, new_pattern, dry_run=True)
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
        old_pattern = data.get('old', 'fr')
        new_pattern = data.get('new', 'fr-fr')
        refresh = data.get('refresh', False)

        results = []

        if asset_id:
            r = api.process_email_asset(asset_id, old_pattern, new_pattern, dry_run=False)
            results.append(r)
        elif journey_id:
            activities, journey = api.get_journey_activities(journey_id)

            for act in activities:
                aid = extract_asset_id(act)
                if aid:
                    r = api.process_email_asset(aid, old_pattern, new_pattern, dry_run=False)
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
        old_pattern = data.get('old', 'fr')
        new_pattern = data.get('new', 'fr-fr')

        activities, journey = api.get_journey_activities(journey_id)
        journey_info = {
            'name': journey.get('name'),
            'status': journey.get('status'),
            'activities_count': len(activities)
        }

        all_urls = []
        activity_results = []

        for act in activities:
            asset_id = extract_asset_id(act)
            if not asset_id:
                continue

            r = api.process_email_asset(asset_id, old_pattern, new_pattern, dry_run=True)

            urls = set()
            if r.get('changes'):
                for change in r['changes']:
                    context = change.get('context', '')
                    found = re.findall(r'https?://[^\s"\'<>]+', context)
                    for url in found:
                        clean = re.split(r'\?sez_client_id=|\?campaign=|&sez_', url)[0]
                        clean = clean.rstrip('?&')
                        if f'/{old_pattern}' in clean and f'/{old_pattern}-' not in clean:
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
