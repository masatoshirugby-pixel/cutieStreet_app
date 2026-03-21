"""
イベント判定モジュール
キーワードマッチング + 日本語形態素解析（fugashi）でイベント告知を判定する。
"""

import logging

try:
    import fugashi
    _FUGASHI_AVAILABLE = True
except ImportError:
    _FUGASHI_AVAILABLE = False

from models import JudgementResult

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# イベントカテゴリ別キーワード定義
# -----------------------------------------------------------------------

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "ライブ": [
        "ライブ", "live", "LIVE", "コンサート", "concert", "公演", "ツアー", "tour",
        "フェス", "festival", "対バン", "ワンマン", "単独", "出演決定",
    ],
    "リリースイベント": [
        "リリースイベント", "リリイベ", "発売記念", "リリース記念",
        "インストア", "in-store", "インストアイベント",
    ],
    "握手会・チェキ会": [
        "握手会", "チェキ会", "チェキ", "お渡し会", "特典会", "個別",
        "サイン会", "ハイタッチ",
    ],
    "メディア出演": [
        "テレビ", "TV", "tv", "ラジオ", "radio", "雑誌", "掲載",
        "出演", "登場", "放送", "オンエア", "オンエアー",
    ],
    "配信イベント": [
        "生配信", "配信ライブ", "オンラインライブ", "無観客", "有観客配信",
        "ニコ生", "YouTube Live", "Streaming", "streaming",
    ],
    "物販・グッズ": [
        "物販", "グッズ", "販売", "通販", "ECショップ", "Tシャツ",
        "フォトセット", "ブロマイド",
    ],
    "その他イベント": [
        "イベント", "event", "EVENT", "参加", "開催", "決定", "告知",
        "お知らせ", "情報解禁", "解禁", "アナウンス",
    ],
}

# 形態素解析で「イベント性」を補強する名詞・動詞
EVENT_NOUNS = {
    "会場", "日程", "チケット", "申込", "予約", "定員", "入場",
    "開場", "開演", "終演", "番組", "収録",
}


def _build_flat_keywords() -> dict[str, str]:
    """キーワード → カテゴリ の逆引き辞書を構築"""
    mapping: dict[str, str] = {}
    for category, words in CATEGORY_KEYWORDS.items():
        for word in words:
            mapping[word.lower()] = category
    return mapping


_KEYWORD_MAP = _build_flat_keywords()


def _keyword_match(text: str) -> tuple[bool, str | None]:
    """
    キーワードマッチング。
    Returns: (is_event, category)
    """
    lower = text.lower()

    # カテゴリ優先順位順にチェック（より具体的なカテゴリを先に）
    priority = [
        "ライブ", "リリースイベント", "握手会・チェキ会",
        "メディア出演", "配信イベント", "物販・グッズ", "その他イベント",
    ]
    for category in priority:
        for word in CATEGORY_KEYWORDS[category]:
            if word.lower() in lower:
                return True, category

    return False, None


def _fugashi_boost(text: str) -> bool:
    """
    形態素解析で EVENT_NOUNS が含まれるかチェック。
    キーワードマッチが曖昧なとき補助的に使う。
    """
    if not _FUGASHI_AVAILABLE:
        return False
    try:
        tagger = fugashi.Tagger()
        for word in tagger(text):
            surface = str(word)
            if surface in EVENT_NOUNS:
                return True
    except Exception as e:
        logger.warning(f"fugashi 解析エラー: {e}")
    return False


def judge_tweet(post_text: str) -> JudgementResult:
    """
    投稿テキストを判定して JudgementResult を返す。
    1. キーワードマッチング（高速・主判定）
    2. 「その他イベント」系キーワードのみマッチした場合、
       fugashi で EVENT_NOUNS が含まれるか確認して信頼度を上げる
    """
    is_event, category = _keyword_match(post_text)

    if not is_event:
        # キーワード不一致でも形態素解析で補強
        if _fugashi_boost(post_text):
            logger.debug("形態素解析でイベント性を検出")
            return JudgementResult(is_event=True, category="その他イベント")
        return JudgementResult(is_event=False, category=None)

    # 「その他イベント」のみの場合、形態素解析で確信度を確認
    if category == "その他イベント" and _FUGASHI_AVAILABLE:
        if not _fugashi_boost(post_text):
            # 「イベント」という単語はあるが関連名詞がない → 除外
            logger.debug("形態素解析でイベント性を否定")
            return JudgementResult(is_event=False, category=None)

    logger.info(f"イベント判定: {category}")
    return JudgementResult(is_event=True, category=category)
