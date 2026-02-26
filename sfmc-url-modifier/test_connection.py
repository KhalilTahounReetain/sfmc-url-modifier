#!/usr/bin/env python3
"""
Test connexion SFMC + liste journeys
"""

import sys

def main():
    print("=" * 50)
    print("Test connexion SFMC")
    print("=" * 50)

    print("\n1. Check config...")
    try:
        from config import SFMC_CLIENT_ID, SFMC_SUBDOMAIN
    except ImportError as e:
        print(f"   ERREUR: {e}")
        sys.exit(1)

    if not SFMC_CLIENT_ID or 'your_' in SFMC_CLIENT_ID:
        print("   ERREUR: Configurer .env")
        sys.exit(1)
    print(f"   OK - {SFMC_SUBDOMAIN}")

    print("\n2. Auth...")
    try:
        from sfmc_auth import SFMCAuth
        auth = SFMCAuth()
        auth.refresh()
    except Exception as e:
        print(f"   ERREUR: {e}")
        sys.exit(1)

    print("\n3. Récupération TOUTES les journeys...")
    try:
        from sfmc_api import SFMCAPI
        api = SFMCAPI(auth)
        data = api.get_all_journeys()
        all_j = data.get('items', [])

        print(f"   Total: {len(all_j)} journeys")

        # Grouper par type
        by_type = {}
        for j in all_j:
            t = j.get('definitionType', 'Unknown')
            by_type[t] = by_type.get(t, 0) + 1

        print(f"   Par type: {by_type}")

        # Filtrer transactionnelles
        transac = [j for j in all_j if j.get('definitionType') == 'Transactional']
        print(f"   Transactionnelles: {len(transac)}")

        print("\n   --- TOUTES LES JOURNEYS ---")
        for j in all_j:
            dtype = j.get('definitionType', '?')
            status = j.get('status', '?')
            marker = " [TRANSAC]" if dtype == 'Transactional' else ""
            print(f"   {j.get('id')}")
            print(f"   {j.get('name')} | {status} | {dtype}{marker}")
            print()

    except Exception as e:
        print(f"   ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("=" * 50)
    print("OK!")
    print("=" * 50)

if __name__ == '__main__':
    main()
