#!/usr/bin/env python3
"""
Test connexion SFMC + liste journeys Welcome
"""

import sys

def is_welcome_journey(journey):
    name = journey.get('name', '').lower()
    return 'welcome' in name

def main():
    print("=" * 50)
    print("Test connexion SFMC - Welcome Journeys")
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

    print("\n3. Récupération journeys...")
    try:
        from sfmc_api import SFMCAPI
        api = SFMCAPI(auth)
        data = api.get_all_journeys()
        all_j = data.get('items', [])

        print(f"   Total: {len(all_j)} journeys")

        # Filtrer Welcome
        welcome = [j for j in all_j if is_welcome_journey(j)]
        print(f"   Welcome: {len(welcome)}")

        print("\n   --- JOURNEYS WELCOME ---")
        for j in welcome:
            status = j.get('status', '?')
            dtype = j.get('definitionType', '?')
            print(f"   {j.get('id')}")
            print(f"   {j.get('name')} | {status} | {dtype}")
            print()

        if not welcome:
            print("   Aucune journey avec 'welcome' dans le nom")

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
