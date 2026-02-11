#!/usr/bin/env python3
from __future__ import annotations

"""
XBloom Recipe Maker CLI.

Commands:
  login                     — Login with email/password (saves to ~/.xbloom_auth)
  fetch <share_url_or_id>   — Fetch a shared recipe (public, no auth)
  create --config recipe.json — Create a recipe (requires login)
  list                      — List my recipes (requires login)
  template                  — Print a blank recipe JSON template
"""

import argparse
import getpass
import json
import sys

import xbloom_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CUP_TYPES = {1: "XPOD", 2: "OMNI", 3: "OTHER", 4: "TEA"}
PATTERNS = {1: "Center", 2: "Circular", 3: "Spiral"}
TOGGLE = {1: "ON", 2: "OFF"}


def _get_member_id() -> int:
    """Load member_id from ~/.xbloom_auth. Exit if not logged in."""
    auth = xbloom_client.load_auth()
    if not auth or not auth.get("member_id"):
        print("Error: 로그인 필요. 먼저 'python recipe_maker.py login' 실행", file=sys.stderr)
        sys.exit(1)
    return int(auth["member_id"])


def _print_recipe(recipe: dict) -> None:
    """Pretty-print a single recipe."""
    print(f"  Name:      {recipe.get('theName', '?')}")
    print(f"  Dose:      {recipe.get('dose', '?')}g")
    print(f"  Ratio:     1:{recipe.get('grandWater', '?')}")
    print(f"  Grind:     {recipe.get('grinderSize', '?')}")
    print(f"  RPM:       {recipe.get('rpm', '?')}")
    print(f"  Cup:       {CUP_TYPES.get(recipe.get('cupType'), recipe.get('cupType', '?'))}")
    print(f"  Color:     {recipe.get('theColor', '?')}")
    print(f"  Bypass:    {TOGGLE.get(recipe.get('isEnableBypassWater'), '?')} ({recipe.get('bypassVolume', '?')}ml @ {recipe.get('bypassTemp', '?')}°C)")
    print(f"  Grinder:   {TOGGLE.get(recipe.get('isSetGrinderSize'), '?')}")

    pours = recipe.get("pourList", [])
    print(f"  Pours ({len(pours)}):")
    for i, p in enumerate(pours, 1):
        pat = PATTERNS.get(p.get("pattern"), p.get("pattern", "?"))
        vib_b = TOGGLE.get(p.get("isEnableVibrationBefore"), "?")
        vib_a = TOGGLE.get(p.get("isEnableVibrationAfter"), "?")
        print(f"    [{i}] {p.get('theName', 'Pour')}: "
              f"{p.get('volume', '?')}ml @ {p.get('temperature', '?')}°C, "
              f"flow={p.get('flowRate', '?')}, pattern={pat}, "
              f"pause={p.get('pausing', 0)}s, "
              f"vib={vib_b}/{vib_a}")

    link = recipe.get("shareRecipeLink", "")
    if link:
        print(f"  Share:     {link}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_login(args: argparse.Namespace) -> int:
    email = args.email or input("Email: ")
    password = args.password or getpass.getpass("Password: ")

    resp = xbloom_client.login(email, password)
    if resp.get("result") != "success":
        print(f"Login failed: {resp.get('info', resp)}", file=sys.stderr)
        return 1

    member = resp.get("member", {})
    print(f"Logged in as {member.get('theName') or member.get('email', '?')} (id={member.get('tableId')})")
    print(f"Auth saved to {xbloom_client.AUTH_FILE}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    resp = xbloom_client.fetch_recipe(args.share_id)
    if resp.get("result") != "success":
        print(f"Error: {resp.get('info', resp)}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0

    rv = resp.get("recipeVo", {})
    author = resp.get("shareMemberName", "?")
    print(f"Recipe by {author}:")
    _print_recipe(rv)
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    member_id = _get_member_id()

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    pour_list = cfg.get("pourList") or cfg.get("pour_list")
    if pour_list is None:
        print("Error: config JSON에 pourList 필드 필요", file=sys.stderr)
        return 1

    resp = xbloom_client.create_recipe(
        member_id,
        name=cfg.get("theName", cfg.get("name", "My Recipe")),
        dose=float(cfg.get("dose", 15.0)),
        grand_water=float(cfg.get("grandWater", cfg.get("grand_water", 15.0))),
        grinder_size=float(cfg.get("grinderSize", cfg.get("grinder_size", 70.0))),
        rpm=int(cfg.get("rpm", 120)),
        cup_type=int(cfg.get("cupType", cfg.get("cup_type", 1))),
        adapted_model=int(cfg.get("adaptedModel", cfg.get("adapted_model", 1))),
        is_enable_bypass_water=int(cfg.get("isEnableBypassWater", 2)),
        is_set_grinder_size=int(cfg.get("isSetGrinderSize", 1)),
        the_color=cfg.get("theColor", cfg.get("the_color", "#C9D5B8")),
        the_subset_id=int(cfg.get("theSubsetId", cfg.get("the_subset_id", 0))),
        bypass_temp=float(cfg.get("bypassTemp", 85.0)),
        bypass_volume=float(cfg.get("bypassVolume", 5.0)),
        pour_list=pour_list,
    )

    if resp.get("result") != "success":
        print(f"Error: {resp.get('info', resp)}", file=sys.stderr)
        return 1

    print(f"Created! tableId={resp.get('tableId')}, version={resp.get('theVersion')}")
    if args.json:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    member_id = _get_member_id()
    resp = xbloom_client.list_my_recipes(member_id)

    if resp.get("result") != "success":
        print(f"Error: {resp.get('info', resp)}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return 0

    recipes = resp.get("list", [])
    print(f"Total: {len(recipes)} recipes\n")
    for i, r in enumerate(recipes, 1):
        print(f"[{i}] {r.get('theName', '?')} (id={r.get('tableId', '?')})")
        _print_recipe(r)
        print()
    return 0


def cmd_template(_args: argparse.Namespace) -> int:
    template = {
        "theName": "My Recipe",
        "dose": 15.0,
        "grandWater": 15.0,
        "grinderSize": 70.0,
        "rpm": 120,
        "cupType": 1,
        "adaptedModel": 1,
        "isEnableBypassWater": 2,
        "isSetGrinderSize": 1,
        "theColor": "#C9D5B8",
        "theSubsetId": 0,
        "bypassTemp": 85.0,
        "bypassVolume": 5.0,
        "pourList": [
            {
                "theName": "Bloom",
                "volume": 50.0,
                "temperature": 93.0,
                "flowRate": 3.0,
                "pattern": 1,
                "pausing": 30,
                "isEnableVibrationBefore": 2,
                "isEnableVibrationAfter": 2,
            },
            {
                "theName": "Main Pour",
                "volume": 175.0,
                "temperature": 93.0,
                "flowRate": 3.5,
                "pattern": 2,
                "pausing": 0,
                "isEnableVibrationBefore": 2,
                "isEnableVibrationAfter": 2,
            },
        ],
    }
    print(json.dumps(template, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Arg parser
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="XBloom Recipe Maker CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # login
    p_login = sub.add_parser("login", help="XBloom 계정 로그인 (한번만 하면 됨)")
    p_login.add_argument("--email", help="이메일")
    p_login.add_argument("--password", help="비밀번호 (생략시 프롬프트)")
    p_login.set_defaults(func=cmd_login)

    # fetch
    p_fetch = sub.add_parser("fetch", help="공유 레시피 조회 (로그인 불필요)")
    p_fetch.add_argument("share_id", help="Share URL 또는 id")
    p_fetch.add_argument("--json", action="store_true", help="원본 JSON 출력")
    p_fetch.set_defaults(func=cmd_fetch)

    # create
    p_create = sub.add_parser("create", help="레시피 생성 (로그인 필요)")
    p_create.add_argument("--config", required=True, help="레시피 JSON 파일")
    p_create.add_argument("--json", action="store_true", help="응답 JSON 출력")
    p_create.set_defaults(func=cmd_create)

    # list
    p_list = sub.add_parser("list", help="내 레시피 목록 (로그인 필요)")
    p_list.add_argument("--json", action="store_true", help="원본 JSON 출력")
    p_list.set_defaults(func=cmd_list)

    # template
    p_tmpl = sub.add_parser("template", help="빈 레시피 JSON 템플릿 출력")
    p_tmpl.set_defaults(func=cmd_template)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
