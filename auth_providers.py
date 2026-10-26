# Copyright 2026 Allan Brand
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://apache.org
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific permissions and
# limitations under the License.

import os
from dotenv import load_dotenv

load_dotenv()

import ldap3
import pyradius

LDAP_SERVER = os.getenv("LDAP_SERVER_IP", "127.0.0.1")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "DC=local")
RADIUS_SERVER = os.getenv("RADIUS_SERVER_IP", "127.0.0.1")
RADIUS_SECRET = os.getenv("RADIUS_SECRET", "fallback_secret").encode('utf-8')

def authenticate_via_active_directory(username: str, plain_password: str) -> bool:
    user_dn = f"CN={username},CN=Users,{LDAP_BASE_DN}"
    try:
        server = ldap3.Server(LDAP_SERVER, get_info=ldap3.ALL)
        connection = ldap3.Connection(server, user=user_dn, password=plain_password, authentication=ldap3.SIMPLE)
        if connection.bind():
            connection.unbind()
            return True
        return False
    except Exception: return False

def authenticate_via_radius(username: str, plain_password: str) -> bool:
    try:
        rad_client = pyradius.Client(RADIUS_SERVER, secret=RADIUS_SECRET)
        return rad_client.authenticate(username, plain_password)
    except Exception: return False
