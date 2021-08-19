import atexit
import json
from pathlib import Path

import requests
import pykakasi

from .settings import DEEPL_API_KEY


DEEPL_CACHE_PATH = Path(__file__).with_name("deepl_cache.json")
try:
    with open(DEEPL_CACHE_PATH) as f:
        DEEPL_CACHE = json.load(f)
except OSError:
    DEEPL_CACHE = {}
atexit.register(lambda: json.dump(DEEPL_CACHE, open(DEEPL_CACHE_PATH, "w")))


BREWERY_JP_EN = {
    "Yマーケット": "Y.Market",
    "うしとらブルワリー": "Ushitora",
    "ろまんちっく村": "Romantic Village",
    "アウトベールセル": "Oud Berseel",
    "アルマナック": "Almanach",
    "アルヴィンヌ": "Alvine",
    "イーヴィル ツイン": "Evil Twin",
    "オムニポロ": "Omnipollo",
    "カルミネーション": "Culmination",
    "キャプテンローレンス": "Captain Lawrence",
    "クルーリパブリック": "CREW Republic",
    "ストーン": "Stone",
    "ノーザンモンク": "Northern Monk",
    "ノースアイランドビール": "North Island Beer",
    "ビアへるん": "Beer Hearn",
    "ファイアーストーンウォーカー": "Firestone Walker",
    "ファウンダーズ": "Founders",
    "ブリュードッグ": "Brewdog",
    "ブレイクサイド": "Breakside",
    "ベアレン": "Bearen",
    "ベアードビール": "Baird",
    "ベルチング ビーバー": "Belching Beaver",
    "ミッケラー": "Mikkeller",
    "ヨロッコビール": "Yorocco",
    "ラーヴィグ": "Lervig",
    "リヴィジョン": "Revision",
    "リーフマンス": "Liefmans",
    "ロコビア": "LOCOBEER",
    "ロストアビィ": "Lost Abbey",
    "ローデンバッハ": "Rodenbach",
    "伊勢角屋麦酒": "Ise Kadoya",
    "反射炉ビヤ": "Hansharo",
    "城端麦酒": "Johana",
    "富士桜高原麦酒": "Fujijzakura",
    "湘南ビール": "Shonan Beer",
    "鬼伝説": "Oni Densetsu",
}

kks = pykakasi.kakasi()


def has_japanese(text: str) -> bool:
    return any(ord(c) > 0x3000 for c in text)


def deepl_translate(text: str) -> str:
    if text in DEEPL_CACHE:
        return text
    res = requests.get(
        "https://api-free.deepl.com/v2/translate",
        params=dict(
            auth_key=DEEPL_API_KEY,
            text=text,
            split_sentences="0",
            source_lang="JA",
            target_lang="EN-US",
        ),
    )
    try:
        translation = res.json()["translations"][0]["text"]
        DEEPL_CACHE[text] = translation
    except Exception as e:
        print(f"DeepL translation failed: {e}")
        translation = text
    return translation


def to_romaji(text: str) -> str:
    result = kks.convert(text)
    return " ".join(item["hepburn"] for item in result)
