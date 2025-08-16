import pykakasi

from ..db import get_db
from .deepl_cache import DeepLSQLiteCache
from .settings import DEEPL_API_KEY
from .utils import get_retrying_session

session = get_retrying_session()

# Initialize SQLite cache
_cache = None


def get_deepl_cache() -> DeepLSQLiteCache:
    """Get or create the DeepL cache instance."""
    global _cache
    if _cache is None:
        _cache = DeepLSQLiteCache(get_db())
    return _cache


BREWERY_JP_EN = {
    "yマーケット": "Y.Market",
    "うしとらブルワリー": "Ushitora",
    "うちゅうブルーイング": "Uchu Brewing",
    "やみぞ森林のビール": "Daigo Shinrinbussan",
    "ろまんちっく村": "Romantic Village",
    "アウトベールセル": "Oud Berseel",
    "アルマナック": "Almanach",
    "アルヴィンヌ": "Alvine",
    "イーヴィル ツイン": "Evil Twin",
    "オムニポロ": "Omnipollo",
    "カマドブリュワリー": "Camado",
    "カルミネーション": "Culmination",
    "キャプテンローレンス": "Captain Lawrence",
    "クルーリパブリック": "CREW Republic",
    "ストーン": "Stone",
    "ソングバード": "Songbird",
    "ディレイラ": "Derailleur",
    "ノーザンモンク": "Northern Monk",
    "ノースアイランドビール": "North Island Beer",
    "ビアへるん": "Beer Hearn",
    "ファイアーストーンウォーカー": "Firestone Walker",
    "ファウンダーズ": "Founders",
    "ブリュードッグ": "Brewdog",
    "ブレイクサイド": "Breakside",
    "ベアレン": "Bearen",
    "ベアレン醸造所": "Bearen",
    "ベアードビール": "Baird",
    "ベルチング ビーバー": "Belching Beaver",
    "ミッケラー": "Mikkeller",
    "ヨロッコビール": "Yorocco",
    "ラーヴィグ": "Lervig",
    "リパブリュー": "Repubrew",
    "リヴィジョン": "Revision",
    "リーフマンス": "Liefmans",
    "ロコビア": "LOCOBEER",
    "ロストアビィ": "Lost Abbey",
    "ローデンバッハ": "Rodenbach",
    "京都醸造": "Kyoto Brewing",
    "伊勢角屋麦酒": "Ise Kadoya",
    "反射炉ビヤ": "Hansharo",
    "城端麦酒": "Johana",
    "富士桜高原麦酒": "Fujijzakura",
    "常陸野ネストビール": "Hitachino",
    "湘南ビール": "Shonan Beer",
    "箕面ビール": "Minoh",
    "鬼伝説": "Oni Densetsu",
}

kks = pykakasi.kakasi()


def has_japanese(text: str) -> bool:
    return any(ord(c) > 0x3000 for c in text)


def deepl_translate(text: str) -> str:
    cache = get_deepl_cache()

    # Check cache first
    cached = cache.get(text)
    if cached is not None:
        return cached

    # Not in cache, call DeepL API
    res = session.get(
        "https://api-free.deepl.com/v2/translate",
        params={
            "auth_key": DEEPL_API_KEY,
            "text": text,
            "split_sentences": "0",
            "source_lang": "JA",
            "target_lang": "EN-US",
        },
    )
    try:
        data = res.json()
        translation: str = data["translations"][0]["text"]
        cache.set(text, translation)
    except Exception as e:
        print(f"DeepL translation failed: {e}")
        translation = text
    return translation


def to_romaji(text: str) -> str:
    result = kks.convert(text)
    return " ".join(item["hepburn"] for item in result)
