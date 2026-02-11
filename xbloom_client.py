from __future__ import annotations

"""
XBloom API Client — reverse-engineered from HAR capture + APK decompilation.

Encryption: Base64(RSA_1024_PKCS1v1.5(JSON))
  - hutool-style chunking: 117 bytes plaintext → 128 bytes ciphertext per block
  - All authenticated endpoints receive the encrypted base64 string as raw POST body

Auth model:
  - skey is a hardcoded app key ("testskey"), NOT a session token (ReleaseKey.java)
  - Real auth = memberId (from login response member.tableId)
  - Login: POST tMemberLogin.thtml (RSA encrypted, email+password)
  - Response: token, member{tableId, theName, email, ...}

Public key from com.chisalsoft.basic.util.RSAEncrypt (BaseTransfer).
"""

import base64
import json
import math
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import unquote

# RSA public key (1024-bit, X.509/PKCS#8 DER, base64)
RSA_PUBLIC_KEY_B64 = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC4LF40GZ72SdhMyl765K/i4nY5"
    "CPcHz2Q1IKWKZ9S79xmK7G8pUhbVf4EZLvnNF1+9IvOFQUKV5Z7ZNNviqSpnql9"
    "tAT+8+J/He0R7pcirvVSxgdr2i9V/C/gmqAEZ5qVTzRnd3uWdFoKzPdEBxP0Ipor"
    "J1VBbCv90yBSOhVxO+QIDAQAB"
)

BASE_URL = "https://client-api.xbloom.com/"
SKEY = "testskey"  # hardcoded in ReleaseKey.java — NOT a session token
AUTH_FILE = Path.home() / ".xbloom_auth"

# RSA 1024: key size 128 bytes, max plaintext per block = 128 - 11 = 117
RSA_KEY_BYTES = 128
RSA_MAX_PLAIN_BLOCK = 117


def _load_rsa_public_key():
    """Load RSA public key. Requires 'cryptography' package."""
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    der = base64.b64decode(RSA_PUBLIC_KEY_B64)
    return load_der_public_key(der)


def rsa_encrypt(plaintext: bytes) -> bytes:
    """
    RSA 1024 PKCS1v1.5 encrypt with hutool-style chunking.
    Splits plaintext into 117-byte blocks, encrypts each to 128-byte ciphertext.
    """
    from cryptography.hazmat.primitives.asymmetric import padding

    pub_key = _load_rsa_public_key()
    num_blocks = math.ceil(len(plaintext) / RSA_MAX_PLAIN_BLOCK)
    ciphertext = bytearray()
    for i in range(num_blocks):
        start = i * RSA_MAX_PLAIN_BLOCK
        end = min(start + RSA_MAX_PLAIN_BLOCK, len(plaintext))
        block = plaintext[start:end]
        encrypted = pub_key.encrypt(block, padding.PKCS1v15())
        ciphertext.extend(encrypted)
    return bytes(ciphertext)


def encrypt_form(form: dict[str, Any]) -> str:
    """JSON serialize → RSA encrypt → base64 encode. Returns the request body string."""
    json_bytes = json.dumps(form, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encrypted = rsa_encrypt(json_bytes)
    return base64.b64encode(encrypted).decode("ascii")


def _make_base_form(member_id: int, token: str = "") -> dict[str, Any]:
    """BaseForm + ProjectForm fields. skey is always "testskey"."""
    auth = load_auth() if not token else None
    return {
        "interfaceVersion": 20240918,
        "skey": SKEY,
        "phoneType": "Android",
        "memberId": member_id,
        "clientType": 2,
        "languageType": 1,
        "token": token or (auth.get("token", "") if auth else ""),
    }


def _post(endpoint: str, body: str | dict, is_encrypted: bool = True) -> dict[str, Any]:
    """
    POST to client-api.xbloom.com.
    - encrypted endpoints: body is a raw base64 string
    - public endpoints: body is JSON
    """
    url = BASE_URL + endpoint
    if is_encrypted:
        data = body.encode("utf-8") if isinstance(body, str) else body
    else:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Accept", "application/json, text/plain, */*")
    if not is_encrypted:
        req.add_header("Referer", "https://share-h5.xbloom.com/")

    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Public API (no auth)
# ---------------------------------------------------------------------------

def parse_share_id(share_url_or_id: str) -> str:
    """Extract the tableIdOfRSA from a share URL or raw id string."""
    s = share_url_or_id.strip()
    if "id=" in s:
        s = s.split("id=")[-1].split("&")[0]
    return unquote(s)


def fetch_recipe(share_url_or_id: str) -> dict[str, Any]:
    """
    Fetch a shared recipe (public, no auth required).
    POST /RecipeDetail.html with plain JSON body.
    Returns full API response dict.
    """
    table_id = parse_share_id(share_url_or_id)
    body = {
        "tableIdOfRSA": table_id,
        "interfaceVersion": 19700101,
        "skey": SKEY,
    }
    return _post("RecipeDetail.html", body, is_encrypted=False)


# ---------------------------------------------------------------------------
# Auth: login + credential storage
# ---------------------------------------------------------------------------

def save_auth(member_id: int, token: str, email: str = "") -> None:
    """Save auth to ~/.xbloom_auth."""
    data = {"member_id": member_id, "token": token, "email": email}
    AUTH_FILE.write_text(json.dumps(data), encoding="utf-8")
    AUTH_FILE.chmod(0o600)


def load_auth() -> dict[str, Any] | None:
    """Load auth from ~/.xbloom_auth. Returns None if not found."""
    if not AUTH_FILE.exists():
        return None
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def login(email: str, password: str) -> dict[str, Any]:
    """
    Login with email + password.
    POST /tMemberLogin.thtml (RSA encrypted).
    Returns full API response with member info + token.
    On success, saves auth to ~/.xbloom_auth.
    """
    form = {
        "interfaceVersion": 20240918,
        "skey": SKEY,
        "phoneType": "Android",
        "clientType": 2,
        "languageType": 1,
        "email": email,
        "password": password,
        "jpushId": "",
    }
    encrypted_body = encrypt_form(form)
    resp = _post("tMemberLogin.thtml", encrypted_body, is_encrypted=True)
    if resp.get("result") == "success":
        member = resp.get("member", {})
        save_auth(
            member_id=int(member.get("tableId", 0)),
            token=resp.get("token", ""),
            email=member.get("email", email),
        )
    return resp


# ---------------------------------------------------------------------------
# Authenticated API (RSA encrypted)
# ---------------------------------------------------------------------------

def create_recipe(
    member_id: int,
    *,
    name: str = "My Recipe",
    dose: float = 15.0,
    grand_water: float = 15.0,
    grinder_size: float = 70.0,
    rpm: int = 120,
    cup_type: int = 1,
    adapted_model: int = 1,
    is_enable_bypass_water: int = 2,
    is_set_grinder_size: int = 1,
    the_color: str = "#C9D5B8",
    the_subset_id: int = 0,
    bypass_temp: float = 85.0,
    bypass_volume: float = 5.0,
    pour_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Create a new recipe.
    POST /tuRecipeAdd.tuhtml (RSA encrypted body).
    Returns API response with tableId of the new recipe.
    """
    if pour_list is None:
        pour_list = [{
            "theName": "Pour",
            "volume": 225.0,
            "temperature": 93.0,
            "flowRate": 3.5,
            "pattern": 1,
            "pausing": 0,
            "isEnableVibrationBefore": 2,
            "isEnableVibrationAfter": 2,
        }]

    form = _make_base_form(member_id)
    form.update({
        "theName": name,
        "dose": dose,
        "grandWater": grand_water,
        "grinderSize": grinder_size,
        "rpm": rpm,
        "cupType": cup_type,
        "adaptedModel": adapted_model,
        "isEnableBypassWater": is_enable_bypass_water,
        "isSetGrinderSize": is_set_grinder_size,
        "theColor": the_color,
        "theSubsetId": the_subset_id,
        "bypassTemp": bypass_temp,
        "bypassVolume": bypass_volume,
        "subSetType": 2,                              # 2=ManMade (사용자 생성)
        "appPlace": [4],                               # 4="내 레시피" 섹션에 표시
        "createTimeStamp": int(time.time() * 1000),    # 현재시간 (ms)
        "isShortcuts": 2,                              # 2=일반 레시피 (바로가기 아님)
        "pourDataJSONStr": json.dumps(pour_list, ensure_ascii=False, separators=(",", ":")),
    })

    encrypted_body = encrypt_form(form)
    return _post("tuRecipeAdd.tuhtml", encrypted_body, is_encrypted=True)


def list_my_recipes(member_id: int, adapted_model: int = 1) -> dict[str, Any]:
    """
    List my created recipes.
    POST /tuMyTeaRecipeCreated.tuhtml (RSA encrypted body).
    adapted_model: 0=all, 1=Original, 2=Studio
    Returns API response with list[] of recipes.
    """
    form = _make_base_form(member_id)
    form["pageNumber"] = 1
    form["countPerPage"] = 100
    if adapted_model:
        form["adaptedModel"] = adapted_model
    encrypted_body = encrypt_form(form)
    return _post("tuMyTeaRecipeCreated.tuhtml", encrypted_body, is_encrypted=True)
