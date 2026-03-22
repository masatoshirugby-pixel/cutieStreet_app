"""
イベント日付抽出・会場抽出・重複検出ユーティリティ
"""

import logging
import re
from datetime import date, datetime, timezone

try:
    import fugashi
    _FUGASHI_AVAILABLE = True
except ImportError:
    _FUGASHI_AVAILABLE = False

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# 日付抽出
# -----------------------------------------------------------------------

# パターン定義: (regex, has_year)
# 対応例: 2026年3月21日 / 3月21日 / 2026/3/21 / 3/21
_DATE_PATTERNS: list[tuple[re.Pattern, bool]] = [
    (re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日"), True),    # 2026年3月21日
    (re.compile(r"(\d{4})/\s*(\d{1,2})/\s*(\d{1,2})"), True),        # 2026/3/21
    (re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})"), True),             # 2026.03.07
    (re.compile(r"(\d{1,2})月\s*(\d{1,2})日"), False),                # 3月21日
    (re.compile(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)"), False),  # 3/21 or "3 /21"
    (re.compile(r"(?<!\d)(\d{2})\s+(\d{2})\s+\[[A-Z]{2,3}\]"), False),  # 03 01 [SUN]
]

# 曜日・補助キーワード（日付の直後に現れやすい）
_DATE_CONTEXT = re.compile(r"[（(][月火水木金土日][）)]|開催|開場|開演|予定")

# 開催日を示す文脈キーワード（直後に日付が来やすい）
_EVENT_DATE_CONTEXT_KEYWORDS = re.compile(
    r"(開催日程|開催日時|開催日|実施日時|実施日|イベント日|日時|日程|開催時間|開演日)\s*[：:：\s]?\s*"
)
# 文脈キーワードから何文字以内の日付を「開催日」と見なすか
_CONTEXT_WINDOW = 60


def extract_event_dates(text: str) -> list[date]:
    """
    テキストから日付を全て抽出して返す。
    年が省略されている場合は今年 or 来年を自動補完する。
    """
    today = datetime.now(timezone.utc).date()
    results: list[date] = []

    for pat, has_year in _DATE_PATTERNS:
        for m in pat.finditer(text):
            try:
                if has_year:
                    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    month, day = int(m.group(1)), int(m.group(2))
                    # 年が省略された場合: 過去3ヶ月より前なら来年と判定
                    year = today.year
                    candidate = date(year, month, day)
                    if (today - candidate).days > 90:
                        year += 1

                d = date(year, month, day)
                # 5年以上前のイベントは URL 等のノイズと判断して除外
                if (today - d).days > 365 * 5:
                    continue
                if d not in results:
                    results.append(d)
            except ValueError:
                pass  # 不正な日付は無視

    return sorted(results)


def _extract_contextual_event_date(text: str) -> date | None:
    """
    「開催日程」「開催日」「日時」などのキーワード直後にある日付を開催日として返す。
    ニュース記事の本文に含まれる公開日ノイズを回避するための補助関数。
    """
    today = datetime.now(timezone.utc).date()

    for kw_match in _EVENT_DATE_CONTEXT_KEYWORDS.finditer(text):
        start = kw_match.end()
        window = text[start: start + _CONTEXT_WINDOW]

        for pat, has_year in _DATE_PATTERNS:
            m = pat.search(window)
            if not m:
                continue
            try:
                if has_year:
                    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    month, day = int(m.group(1)), int(m.group(2))
                    year = today.year
                    candidate = date(year, month, day)
                    if (today - candidate).days > 90:
                        year += 1

                d = date(year, month, day)
                if (today - d).days > 365 * 5:
                    continue
                return d
            except ValueError:
                pass

    return None


def extract_event_date(text: str) -> date | None:
    """
    イベント日付を返す。
    1. 開催日程・日時などのキーワード周辺から文脈的に抽出（ニュース記事の公開日ノイズ対策）
    2. タイトル部分（冒頭200文字）
    3. 全文から最初の日付
    """
    contextual = _extract_contextual_event_date(text)
    if contextual:
        return contextual

    head_dates = extract_event_dates(text[:200])
    if head_dates:
        return head_dates[0]
    dates = extract_event_dates(text)
    return dates[0] if dates else None


# -----------------------------------------------------------------------
# 対象アカウント定義
# -----------------------------------------------------------------------

ACCOUNTS: list[str] = [
    "CUTIE_STREET_",
    "CANDY_TUNE_",
    "SWEET_STEADY",
]

# -----------------------------------------------------------------------
# 会場抽出
# -----------------------------------------------------------------------

_VENUE_PATTERNS = [
    re.compile(r"(ベルサール\S+)"),
    re.compile(r"(Zepp\s*\S+)", re.IGNORECASE),
    re.compile(r"(LIQUIDROOM|リキッドルーム)"),
    re.compile(r"(豊洲PIT|豊洲ピット)"),
    re.compile(r"(Zepp\S+)"),
    re.compile(r"(\S+ホール)"),
    re.compile(r"(\S+アリーナ)"),
    re.compile(r"(\S+CLUB\s*\S+)", re.IGNORECASE),
    re.compile(r"(\S+劇場)"),
    re.compile(r"(\S+会館)"),
    re.compile(r"(\S+センター)"),
]


def extract_venue(text: str) -> str | None:
    """テキストから会場名を抽出する。最初にマッチしたものを返す。"""
    for pat in _VENUE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    return None


# -----------------------------------------------------------------------
# 重複検出
# -----------------------------------------------------------------------

def _extract_keywords(text: str) -> set[str]:
    """
    重複判定用キーワードセットを抽出する。
    fugashi が使えれば名詞を、なければ単語分割で対応。
    """
    if _FUGASHI_AVAILABLE:
        try:
            tagger = fugashi.Tagger()
            nouns = set()
            for word in tagger(text):
                # 品詞が名詞のものを取得（ipadic の品詞情報を利用）
                feature = word.feature
                if hasattr(feature, 'pos') and feature.pos == '名詞':
                    surface = str(word)
                    if len(surface) >= 2:  # 1文字名詞はノイズが多いので除外
                        nouns.add(surface)
            return nouns
        except Exception as e:
            logger.warning(f"fugashi キーワード抽出エラー: {e}")

    # fallback: スペース・記号で分割
    tokens = re.split(r"[\s\u3000、。！？!?「」【】\(\)（）]+", text)
    return {t for t in tokens if len(t) >= 2}


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """2つのテキストのキーワードに基づく Jaccard 類似度を返す。"""
    set_a = _extract_keywords(text_a)
    set_b = _extract_keywords(text_b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def is_duplicate(
    new_text: str,
    new_category: str | None,
    new_event_date: date | None,
    existing_records: list[dict],
    date_match_threshold: int = 0,     # 同日のみ重複とみなす（日付ズレは許容しない）
    similarity_threshold: float = 0.35, # 日付なし時の Jaccard 閾値
) -> bool:
    """
    新規投稿が既存DBレコードと同一イベントかどうかを判定する。

    判定ロジック:
    1. 日付あり: 同カテゴリ & 同日 → 重複
    2. 日付なし: 同カテゴリ & Jaccard類似度 >= similarity_threshold → 重複
    """
    for rec in existing_records:
        # カテゴリが違えば別イベントとみなす
        if rec.get("category") != new_category:
            continue

        rec_date_str: str | None = rec.get("event_date")

        if new_event_date and rec_date_str:
            # 両方に日付がある場合: 日付の近さで判定
            try:
                rec_date = date.fromisoformat(rec_date_str)
                delta = abs((new_event_date - rec_date).days)
                if delta <= date_match_threshold:
                    logger.info(
                        f"重複検出（日付一致）: category={new_category} "
                        f"new={new_event_date} existing={rec_date}"
                    )
                    return True
            except ValueError:
                pass
        else:
            # 日付が取れない場合: テキスト類似度で判定
            sim = jaccard_similarity(new_text, rec.get("post_text", ""))
            if sim >= similarity_threshold:
                logger.info(
                    f"重複検出（類似度）: category={new_category} "
                    f"similarity={sim:.2f}"
                )
                return True

    return False
