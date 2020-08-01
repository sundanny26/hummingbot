import time
import hashlib
import hmac
from typing import Any, Dict


class AltmarketsAuth:
    """
    Auth class required by AltMarkets.io API
    Learn more at https://altmarkets.io
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_signature(self) -> (Dict[str, Any]):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """
        nonce = str(int(time.time() * 1e3))
        auth_payload = nonce + self.api_key
        signature = hmac.new(bytes(self.secret_key, 'latin-1'), msg=bytes(auth_payload, 'latin-1'), digestmod=hashlib.sha256).hexdigest()

        return signature, nonce

    def get_headers(self) -> (Dict[str, Any]):
        signature, nonce = self.generate_signature()
        return {
            "X-Auth-Apikey": self.api_key,
            "X-Auth-Nonce": nonce,
            "X-Auth-Signature": signature,
            "Content-Type": "application/json"
        }
