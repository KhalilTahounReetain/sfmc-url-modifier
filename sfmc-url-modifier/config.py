import os
from dotenv import load_dotenv

load_dotenv()

# Credentials SFMC - à récupérer depuis Setup > Apps > Installed Packages
SFMC_CLIENT_ID = os.getenv('SFMC_CLIENT_ID')
SFMC_CLIENT_SECRET = os.getenv('SFMC_CLIENT_SECRET')
SFMC_SUBDOMAIN = os.getenv('SFMC_SUBDOMAIN')
SFMC_MID = os.getenv('SFMC_MID')

# Endpoints API
AUTH_URL = f"https://{SFMC_SUBDOMAIN}.auth.marketingcloudapis.com/v2/token"
REST_BASE_URL = f"https://{SFMC_SUBDOMAIN}.rest.marketingcloudapis.com"

# Mapping pays pour les remplacements d'URL
COUNTRY_MAPPINGS = {
    'fr': 'fr-fr',
    'de': 'de-de',
    'es': 'es-es',
    'it': 'it-it',
}
