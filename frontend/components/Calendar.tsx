"use client";

import { useState } from "react";
import { Event } from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  ライブ: "bg-pink-400 text-white",
  リリースイベント: "bg-purple-400 text-white",
  "握手会・チェキ会": "bg-yellow-400 text-white",
  メディア出演: "bg-blue-400 text-white",
  配信イベント: "bg-green-400 text-white",
  "物販・グッズ": "bg-orange-400 text-white",
  その他イベント: "bg-gray-400 text-white",
};

const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstWeekday(year: number, month: number) {
  const d = new Date(year, month, 1).getDay();
  return d === 0 ? 6 : d - 1; // 月曜始まり
}

function formatEventDate(iso: string) {
  return new Date(iso).toLocaleDateString("ja-JP", {
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

  const daysInMonth = getDaysInMonth(year, month);
  const firstWeekday = getFirstWeekday(year, month);

  // event_date があるイベントを日付でグループ化
  const eventsByDate: Record<string, Event[]> = {};
  for (const event of events) {
    if (!event.event_date) continue;
    const d = new Date(event.event_date + "T00:00:00");
    if (d.getFullYear() === year && d.getMonth() === month) {
      const key = d.getDate().toString();
      if (!eventsByDate[key]) eventsByDate[key] = [];
      eventsByDate[key].push(event);
    }
  }

  // event_date がないイベント
  const undatedEvents = events.filter((e) => !e.event_date);

  function prevMonth() {
    if (month === 0) { setYear(y => y - 1); setMonth(11); }
    else setMonth(m => m - 1);
    setSelected(null);
  }

  function nextMonth() {
    if (month === 11) { setYear(y => y + 1); setMonth(0); }
    else setMonth(m => m + 1);
    setSelected(null);
  }

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      {/* カレンダー本体 */}
      <div className="flex-1">
        {/* 月ナビゲーション */}
        <div className="flex items-center justify-between mb-4">
          <button onClick={prevMonth} className="px-3 py-1 rounded hover:bg-gray-100 text-lg">◀</button>
          <h2 className="text-xl font-bold text-gray-700">{year}年{month + 1}月</h2>
          <button onClick={nextMonth} className="px-3 py-1 rounded hover:bg-gray-100 text-lg">▶</button>
        </div>

        {/* 曜日ヘッダー */}
        <div className="grid grid-cols-7 mb-1">
          {WEEKDAYS.map((d, i) => (
            <div key={d} className={`text-center text-xs font-semibold py-1 ${i === 5 ? "text-blue-500" : i === 6 ? "text-red-500" : "text-gray-500"}`}>
              {d}
            </div>
          ))}
        </div>

        {/* 日付グリッド */}
        <div className="grid grid-cols-7 gap-1">
          {/* 空白（月頭） */}
          {Array.from({ length: firstWeekday }).map((_, i) => (
            <div key={`empty-${i}`} />
          ))}
          {/* 日付セル */}
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
                className={`min-h-16 rounded-lg p-1 border ${isToday ? `border-${accentColor}-400 bg-${accentColor}-50` : "border-gray-100 bg-white"}`}
              >
                <div className={`text-xs font-medium mb-1 ${isToday ? `text-${accentColor}-600 font-bold` : "text-gray-600"}`}>
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
                      {ev.category ?? "イベント"}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* 日付不明イベント */}
        {undatedEvents.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-gray-500 mb-2">日程未確定</h3>
            <div className="flex flex-col gap-2">
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
          </div>
        )}
      </div>

      {/* 右パネル：イベント詳細 + ツイート参照 */}
      <div className="w-full lg:w-80 shrink-0">
        {selected ? (
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm p-5 sticky top-4">
            {/* カテゴリ */}
            {selected.category && (
              <span className={`text-xs font-bold px-2 py-1 rounded-full ${CATEGORY_COLORS[selected.category] ?? CATEGORY_COLORS["その他イベント"]}`}>
                {selected.category}
              </span>
            )}

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

            {/* 画像 */}
            {selected.image_url && (
              <img
                src={selected.image_url}
                alt="イベント画像"
                className="w-full rounded-lg mt-3 object-cover max-h-48"
              />
            )}

            {/* ツイート本文 */}
            <div className="mt-3 p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500 leading-relaxed whitespace-pre-wrap">
                {selected.post_text}
              </p>
              <p className="text-xs text-gray-400 mt-1 text-right">
                {formatPostedAt(selected.posted_at)} 投稿
              </p>
            </div>

            {/* Xリンク */}
            <a
              href={selected.post_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-3 text-xs text-blue-500 hover:text-blue-700 underline"
            >
              𝕏 元の投稿を見る →
            </a>
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
