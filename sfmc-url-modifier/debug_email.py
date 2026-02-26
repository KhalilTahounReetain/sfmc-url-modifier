#!/usr/bin/env python3
"""
Debug contenu email SFMC
Usage: python debug_email.py <asset_id>
"""

import json
import sys
import re
from sfmc_auth import SFMCAuth
from sfmc_api import SFMCAPI


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_email.py <asset_id>")
        sys.exit(1)

    asset_id = sys.argv[1]
    print(f"=== Debug: {asset_id} ===\n")

    auth = SFMCAuth()
    api = SFMCAPI(auth)
    auth.get_token()

    try:
        asset = api.get_asset_by_id(asset_id)
    except Exception as e:
        print(f"Erreur: {e}")
        return

    print(f"Nom: {asset.get('name')}")
    print(f"ID: {asset.get('id')}")
    print(f"Type: {asset.get('assetType', {}).get('name')}")

    # Trouver HTML
    html = None
    if 'views' in asset and 'html' in asset['views']:
        html = asset['views']['html'].get('content', '')
        print(f"Location: views.html.content")
    elif 'content' in asset:
        html = asset.get('content', '')
        print(f"Location: content")
    elif 'data' in asset:
        html = asset.get('data', {}).get('email', {}).get('htmlBody', '')
        if html:
            print(f"Location: data.email.htmlBody")

    if html:
        print(f"Taille: {len(html)} chars\n")

        # URLs /fr
        fr = re.findall(r'["\']([^"\']*\/fr[\/"\'][^"\']*)', html)
        print(f"URLs /fr: {len(fr)}")
        for u in fr[:10]:
            print(f"  {u[:80]}")

        # URLs /fr-fr
        frfr = re.findall(r'["\']([^"\']*\/fr-fr[^"\']*)["\']', html)
        print(f"\nURLs /fr-fr: {len(frfr)}")
        for u in frfr[:10]:
            print(f"  {u[:80]}")
    else:
        print("HTML non trouvé!")

    # Export
    with open(f'debug_{asset_id}.json', 'w') as f:
        json.dump(asset, f, indent=2)
    print(f"\nExport: debug_{asset_id}.json")


if __name__ == '__main__':
    main()
