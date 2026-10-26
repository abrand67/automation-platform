# file: auth_providers.py
import os
import ldap3
import pyradius

LDAP_SERVER = os.getenv("LDAP_SERVER_IP", "10.10.10.5")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "DC=corporate,DC=local")
RADIUS_SERVER = os.getenv("RADIUS_SERVER_IP", "10.10.10.6")
RADIUS_SECRET = b"CorporateSharedRadiusSecret123!"

def authenticate_via_active_directory(username: str, plain_password: str) -> bool:
    """
    Attempts secure bind handshake directly with enterprise Active Directory / LDAP servers.
    """
    user_dn = f"CN={username},CN=Users,{LDAP_BASE_DN}"
    try:
        server = ldap3.Server(LDAP_SERVER, get_info=ldap3.ALL)
        connection = ldap3.Connection(server, user=user_dn, password=plain_password, authentication=ldap3.SIMPLE)
        if connection.bind():
            connection.unbind()
            return True
        return False
    except Exception:
        return False

def authenticate_via_radius(username: str, plain_password: str) -> bool:
    """
    Validates user credentials by transmitting an Access-Request challenge packet to a RADIUS server.
    """
    try:
        rad_client = pyradius.Client(RADIUS_SERVER, secret=RADIUS_SECRET)
        # Transmits access request protocol over default standard port 1812
        return rad_client.authenticate(username, plain_password)
    except pyradius.AuthenticationFailure:
        return False
    except Exception:
        return False

