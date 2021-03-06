import requests
import pykakasi

from .settings import DEEPL_API_KEY


BREWERY_JP_EN = {
    "ビアへるん": "Beer Hearn",
    "ベアレン": "Bearen",
    "Yマーケット": "Y.Market",
    "カルミネーション": "Culmination",
    "ロコビア": "LOCOBEER",
    "ロストアビィ": "Lost Abbey",
    "ミッケラー": "Mikkeller",
    "ヨロッコビール": "Yorocco",
    "伊勢角屋麦酒": "Ise Kadoya",
    "ブリュードッグ": "Brewdog",
    "反射炉ビヤ": "Hansharo",
    "ベルチング ビーバー": "Belching Beaver",
    "リーフマンス": "Liefmans",
    "ノーザンモンク": "Northern Monk",
    "ファウンダーズ": "Founders",
    "ラーヴィグ": "Lervig",
    "湘南ビール": "Shonan Beer",
    "イーヴィル ツイン": "Evil Twin",
    "ストーン": "Stone",
    "ローデンバッハ": "Rodenbach",
    "ブレイクサイド": "Breakside",
    "ノースアイランドビール": "North Island Beer",
    "リヴィジョン": "Revision",
    "オムニポロ": "Omnipollo",
    "キャプテンローレンス": "Captain Lawrence",
    "アルマナック": "Almanach",
    "クルーリパブリック": "CREW Republic",
    "ベアードビール": "Baird",
    "アルヴィンヌ": "Alvine",
    "ファイアーストーンウォーカー": "Firestone Walker",
    "アウトベールセル": "Oud Berseel",
    "鬼伝説": "Oni Densetsu",
}

kks = pykakasi.kakasi()


def has_japanese(text: str) -> bool:
    return any(ord(c) > 0x3000 for c in text)


def deepl_translate(text: str) -> str:
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
    return res.json()["translations"][0]["text"]


def to_romaji(text: str) -> str:
    result = kks.convert(text)
    return " ".join(item["hepburn"] for item in result)
