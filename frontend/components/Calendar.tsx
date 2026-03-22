"use client";

import { useState, useRef, useEffect } from "react";
import { Event } from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  大特典会: "bg-amber-400 text-white",
  特典会: "bg-yellow-400 text-white",
  オンラインサイン会: "bg-teal-400 text-white",
  単独ライブ: "bg-pink-600 text-white",
  合同ライブ: "bg-pink-400 text-white",
  フェス出演: "bg-lime-500 text-white",
  ライブ: "bg-pink-500 text-white",
  リリースイベント: "bg-purple-400 text-white",
  メディア出演: "bg-blue-400 text-white",
  配信イベント: "bg-green-400 text-white",
  "物販・グッズ": "bg-orange-400 text-white",
  その他イベント: "bg-gray-400 text-white",
  申込締切: "bg-red-500 text-white",
  販売・発売: "bg-orange-500 text-white",
  当選通知: "bg-yellow-500 text-white",
  アップグレード通知: "bg-amber-500 text-white",
};

const FILTER_CATEGORIES = [
  "大特典会",
  "特典会",
  "オンラインサイン会",
  "単独ライブ",
  "合同ライブ",
  "フェス出演",
  "ライブ",
  "リリースイベント",
  "メディア出演",
  "配信イベント",
  "物販・グッズ",
  "販売・発売",
  "申込締切",
];

const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstWeekday(year: number, month: number) {
  const d = new Date(year, month, 1).getDay();
  return d === 0 ? 6 : d - 1;
}

function formatEventDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString("ja-JP", {
    timeZone: "Asia/Tokyo",
    month: "long",
    day: "numeric",
    weekday: "short",
  });
}

function formatPostedAt(iso: string) {
  return new Date(iso).toLocaleString("ja-JP", {
    timeZone: "Asia/Tokyo",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface Props {
  events: Event[];
  accentColor: string;
}

export default function Calendar({ events, accentColor }: Props) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selected, setSelected] = useState<Event | null>(null);
  const [undatedOpen, setUndatedOpen] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // ドロップダウン外クリックで閉じる
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function toggleCategory(cat: string) {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }

  const isFiltered = selectedCategories.size > 0;

  const daysInMonth = getDaysInMonth(year, month);
  const firstWeekday = getFirstWeekday(year, month);

  // カテゴリフィルター適用（カレンダー表示用）
  const displayEvents = isFiltered
    ? events.filter((e) => selectedCategories.has(e.category ?? ""))
    : events;

  // event_date があるイベントを日付でグループ化
  const eventsByDate: Record<string, Event[]> = {};
  for (const event of displayEvents) {
    if (!event.event_date) continue;
    const d = new Date(event.event_date + "T00:00:00");
    if (d.getFullYear() === year && d.getMonth() === month) {
      const key = d.getDate().toString();
      if (!eventsByDate[key]) eventsByDate[key] = [];
      eventsByDate[key].push(event);
    }
  }

  // event_date がないイベント
  const undatedEvents = displayEvents.filter((e) => !e.event_date);

  // 選択イベントに関連する申込締切（全eventsから、フィルターに関わらず検索）
  const relatedDeadlines =
    selected?.event_date && selected.category !== "申込締切"
      ? events
          .filter(
            (e) =>
              e.category === "申込締切" &&
              e.account === selected.account &&
              e.event_date !== null &&
              new Date(e.event_date) <= new Date(selected.event_date!) &&
              new Date(selected.event_date!).getTime() -
                new Date(e.event_date).getTime() <=
                45 * 24 * 60 * 60 * 1000
          )
          .sort(
            (a, b) =>
              new Date(a.event_date!).getTime() -
              new Date(b.event_date!).getTime()
          )
      : [];

  // 申込締切クリック時：この締切が対応する先のイベントを検索
  const linkedEvent =
    selected?.category === "申込締切" && selected.event_date
      ? events
          .filter(
            (e) =>
              e.account === selected.account &&
              e.category !== "申込締切" &&
              e.event_date !== null &&
              new Date(e.event_date) >= new Date(selected.event_date!) &&
              new Date(e.event_date).getTime() -
                new Date(selected.event_date!).getTime() <=
                45 * 24 * 60 * 60 * 1000
          )
          .sort(
            (a, b) =>
              new Date(a.event_date!).getTime() -
              new Date(b.event_date!).getTime()
          )[0] ?? null
      : null;

  function prevMonth() {
    if (month === 0) {
      setYear((y) => y - 1);
      setMonth(11);
    } else setMonth((m) => m - 1);
    setSelected(null);
  }

  function nextMonth() {
    if (month === 11) {
      setYear((y) => y + 1);
      setMonth(0);
    } else setMonth((m) => m + 1);
    setSelected(null);
  }

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      {/* カレンダー本体 */}
      <div className="flex-1">
        {/* カテゴリフィルター */}
        <div className="flex items-center gap-2 mb-3" ref={dropdownRef}>
          <div className="relative">
            <button
              onClick={() => setDropdownOpen((v) => !v)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                isFiltered
                  ? "bg-gray-700 text-white border-gray-700"
                  : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
              }`}
            >
              <span>絞り込み</span>
              {isFiltered && (
                <span className="bg-white text-gray-800 rounded-full px-1.5 leading-tight">
                  {selectedCategories.size}
                </span>
              )}
              <span className="text-gray-400">{dropdownOpen ? "▲" : "▼"}</span>
            </button>

            {dropdownOpen && (
              <div className="absolute left-0 top-9 z-50 w-52 bg-white border border-gray-200 rounded-xl shadow-lg py-1 overflow-hidden">
                {FILTER_CATEGORIES.map((cat) => {
                  const checked = selectedCategories.has(cat);
                  const colorDot = CATEGORY_COLORS[cat] ?? CATEGORY_COLORS["その他イベント"];
                  return (
                    <label
                      key={cat}
                      className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleCategory(cat)}
                        className="w-3.5 h-3.5 accent-gray-700"
                      />
                      <span className={`inline-block w-2 h-2 rounded-full ${colorDot.split(" ")[0]}`} />
                      <span className="text-xs text-gray-700">{cat}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {isFiltered && (
            <button
              onClick={() => setSelectedCategories(new Set())}
              className="text-xs text-gray-400 hover:text-gray-600 underline"
            >
              クリア
            </button>
          )}

          {isFiltered && (
            <div className="flex flex-wrap gap-1">
              {[...selectedCategories].map((cat) => (
                <span
                  key={cat}
                  className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    CATEGORY_COLORS[cat] ?? CATEGORY_COLORS["その他イベント"]
                  }`}
                >
                  {cat}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 月ナビゲーション */}
        <div className="flex items-center justify-between mb-4">
          <button onClick={prevMonth} className="px-3 py-1 rounded hover:bg-gray-100 text-lg">◀</button>
          <h2 className="text-xl font-bold text-gray-700">{year}年{month + 1}月</h2>
          <button onClick={nextMonth} className="px-3 py-1 rounded hover:bg-gray-100 text-lg">▶</button>
        </div>

        {/* 曜日ヘッダー */}
        <div className="grid grid-cols-7 mb-1">
          {WEEKDAYS.map((d, i) => (
            <div
              key={d}
              className={`text-center text-xs font-semibold py-1 ${
                i === 5 ? "text-blue-500" : i === 6 ? "text-red-500" : "text-gray-500"
              }`}
            >
              {d}
            </div>
          ))}
        </div>

        {/* 日付グリッド */}
        <div className="grid grid-cols-7 gap-1">
          {Array.from({ length: firstWeekday }).map((_, i) => (
            <div key={`empty-${i}`} />
          ))}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const day = i + 1;
            const dayEvents = eventsByDate[day.toString()] ?? [];
            const isToday =
              today.getFullYear() === year &&
              today.getMonth() === month &&
              today.getDate() === day;

            return (
              <div
                key={day}
                className={`min-h-16 rounded-lg p-1 border ${
                  isToday
                    ? `border-${accentColor}-400 bg-${accentColor}-50`
                    : "border-gray-100 bg-white"
                }`}
              >
                <div
                  className={`text-xs font-medium mb-1 ${
                    isToday ? `text-${accentColor}-600 font-bold` : "text-gray-600"
                  }`}
                >
                  {day}
                </div>
                <div className="flex flex-col gap-0.5">
                  {dayEvents.map((ev) => (
                    <button
                      key={ev.post_id}
                      onClick={() => setSelected(ev)}
                      className={`text-left text-xs px-1 py-0.5 rounded truncate w-full ${
                        CATEGORY_COLORS[ev.category ?? ""] ?? CATEGORY_COLORS["その他イベント"]
                      } ${selected?.post_id === ev.post_id ? "ring-2 ring-offset-1 ring-gray-400" : ""}`}
                    >
                      {ev.category === "申込締切" && ev.venue
                        ? ev.venue
                        : `${ev.category ?? "イベント"}${ev.category !== "申込締切" && ev.post_text?.includes("先着") ? "（先着）" : ""}`}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* 日付不明イベント（プルダウン） */}
        {undatedEvents.length > 0 && (
          <div className="mt-6">
            <button
              onClick={() => setUndatedOpen((o) => !o)}
              className="flex items-center gap-2 text-sm font-semibold text-gray-500 hover:text-gray-700 w-full text-left"
            >
              <span className={`transition-transform duration-200 ${undatedOpen ? "rotate-90" : ""}`}>▶</span>
              日程未確定
              <span className="ml-1 text-xs bg-gray-200 text-gray-600 rounded-full px-2 py-0.5">
                {undatedEvents.length}
              </span>
            </button>
            {undatedOpen && (
              <div className="flex flex-col gap-2 mt-2">
                {undatedEvents.map((ev) => (
                  <button
                    key={ev.post_id}
                    onClick={() => setSelected(ev)}
                    className={`text-left px-3 py-2 rounded-lg text-sm ${
                      CATEGORY_COLORS[ev.category ?? ""] ?? CATEGORY_COLORS["その他イベント"]
                    } ${selected?.post_id === ev.post_id ? "ring-2 ring-offset-1 ring-gray-400" : ""}`}
                  >
                    {ev.category} — {ev.post_text.slice(0, 40)}…
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 右パネル：イベント詳細 */}
      <div className="w-full lg:w-80 shrink-0">
        {selected ? (
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm p-5 sticky top-4">
            {/* カテゴリ */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {selected.category && (
                <span
                  className={`text-xs font-bold px-2 py-1 rounded-full ${
                    CATEGORY_COLORS[selected.category] ?? CATEGORY_COLORS["その他イベント"]
                  }`}
                >
                  {selected.category}
                </span>
              )}
              {selected.category !== "申込締切" && selected.post_text?.includes("先着") && (
                <span className="text-xs font-bold px-2 py-1 rounded-full bg-green-100 text-green-700">
                  先着順
                </span>
              )}
            </div>

            {/* 申込締切クリック時：対象イベント情報を表示 */}
            {selected.category === "申込締切" ? (
              <>
                {selected.event_date && (
                  <p className="text-lg font-bold text-red-600 mt-2">
                    {selected.venue ?? "締切"}：{formatEventDate(selected.event_date)}
                  </p>
                )}
                {linkedEvent ? (
                  <div className="mt-3 bg-pink-50 border border-pink-200 rounded-lg px-3 py-2">
                    <p className="text-xs font-bold text-pink-600 mb-1">対象イベント</p>
                    <p className="text-sm font-semibold text-gray-800">
                      {linkedEvent.category} — {linkedEvent.event_date ? formatEventDate(linkedEvent.event_date) : "日程未定"}
                    </p>
                    {linkedEvent.venue && (
                      <p className="text-xs text-gray-500 mt-0.5">📍 {linkedEvent.venue}</p>
                    )}
                    {linkedEvent.post_url && (
                      <a
                        href={linkedEvent.post_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-block mt-2 text-xs text-blue-500 hover:text-blue-700 underline"
                      >
                        {linkedEvent.source === "x" ? "𝕏 元の投稿を見る →" : "🌐 公式ページを見る →"}
                      </a>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 mt-2">対応するイベントが見つかりません</p>
                )}
                <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 leading-relaxed whitespace-pre-wrap">
                    {selected.post_text.replace("【メール】", "")}
                  </p>
                </div>
              </>
            ) : (
              <>
                {/* イベント日 */}
                {selected.event_date && (
                  <p className="text-lg font-bold text-gray-800 mt-2">
                    {formatEventDate(selected.event_date)}
                  </p>
                )}

                {/* 会場 */}
                {selected.venue && (
                  <p className="text-sm text-gray-600 mt-1">📍 {selected.venue}</p>
                )}

                {/* 申込締切（関連メール） */}
                {relatedDeadlines.length > 0 && (
                  <div className="mt-3 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                    <p className="text-xs font-bold text-red-500 mb-1">📅 申込締切</p>
                    {relatedDeadlines.map((d) => (
                      <p key={d.post_id} className="text-xs text-red-700 mt-0.5">
                        {d.venue ?? "締切"}：{formatEventDate(d.event_date!)}
                      </p>
                    ))}
                  </div>
                )}

                {/* 画像 */}
                {selected.image_url && (
                  <img
                    src={selected.image_url}
                    alt="イベント画像"
                    className="w-full rounded-lg mt-3 object-cover max-h-48"
                  />
                )}

                {/* 本文 */}
                <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 leading-relaxed whitespace-pre-wrap">
                    {selected.post_text}
                  </p>
                  <p className="text-xs text-gray-400 mt-1 text-right">
                    {formatPostedAt(selected.posted_at)} 投稿
                  </p>
                </div>
              </>
            )}

            {/* ソースリンク */}
            {selected.post_url && (
              <a
                href={selected.post_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block mt-3 text-xs text-blue-500 hover:text-blue-700 underline"
              >
                {selected.source === "x" ? "𝕏 元の投稿を見る →" : "🌐 公式ページを見る →"}
              </a>
            )}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-8 text-center text-sm text-gray-400 sticky top-4">
            カレンダーのイベントをクリックすると詳細が表示されます
          </div>
        )}
      </div>
    </div>
  );
}
