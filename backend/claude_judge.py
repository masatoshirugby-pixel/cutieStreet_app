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
    "大特典会": [
        "大特典会",
    ],
    "オンラインサイン会": [
        "オンラインサイン会", "オンラインサイン",
    ],
    "特典会": [
        "特典会", "チェキ会", "チェキ", "お渡し会", "個別握手", "サイン会", "ハイタッチ",
    ],
    "リリースイベント": [
        "リリースイベント", "リリイベ", "発売記念", "リリース記念",
        "インストア", "in-store", "インストアイベント",
    ],
    "単独ライブ": [
        "ワンマン", "ワンマンライブ", "単独公演", "単独ライブ",
    ],
    "フェス出演": [
        "フェス", "festival", "フェスティバル",
    ],
    "合同ライブ": [
        "対バン", "対バンライブ", "合同ライブ", "合同公演", "合同イベント",
    ],
    "ライブ": [
        "ライブ", "live", "LIVE", "コンサート", "concert", "公演", "ツアー", "tour",
        "出演決定",
    ],
    "テレビ出演": [
        "テレビ", "TV", "tv", "放送", "オンエア", "オンエアー", "地上波", "BS", "CS",
    ],
    "ラジオ出演": [
        "ラジオ", "radio", "RADIO",
    ],
    "雑誌掲載": [
        "雑誌", "掲載", "グラビア", "表紙", "誌面",
    ],
    "その他メディア": [
        "出演", "登場",
    ],
    "配信イベント": [
        "生配信", "配信ライブ", "オンラインライブ", "無観客", "有観客配信",
        "ニコ生", "YouTube Live", "Streaming", "streaming",
    ],
    "物販・グッズ": [
        "物販", "グッズ", "通販", "ECショップ", "Tシャツ",
        "フォトセット", "ブロマイド",
    ],
    "販売・発売": [
        "一番くじ", "一番賞", "ichiban kuji",
        "販売開始", "発売開始", "発売日", "発売決定", "発売予定",
        "予約開始", "予約受付", "受注開始", "受注受付",
        "店頭販売", "通販開始", "オンライン販売",
        "CD発売", "BD発売", "DVD発売", "アルバム発売", "シングル発売",
        "フィギュア", "ぬいぐるみ", "アクリルスタンド", "トレカ",
    ],
    "その他イベント": [
        "イベント", "event", "EVENT", "参加", "開催", "決定", "告知",
        "お知らせ", "情報解禁", "解禁", "アナウンス",
        "受付開始", "受付終了", "受付期間", "申込受付",
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
        "大特典会", "オンラインサイン会", "リリースイベント", "特典会",
        "単独ライブ", "フェス出演", "合同ライブ", "ライブ",
        "テレビ出演", "ラジオ出演", "雑誌掲載", "その他メディア",
        "配信イベント", "物販・グッズ", "その他イベント",
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
