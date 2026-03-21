import { Event } from "@/lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  ライブ: "bg-pink-100 text-pink-700",
  リリースイベント: "bg-purple-100 text-purple-700",
  "握手会・チェキ会": "bg-yellow-100 text-yellow-700",
  メディア出演: "bg-blue-100 text-blue-700",
  配信イベント: "bg-green-100 text-green-700",
  "物販・グッズ": "bg-orange-100 text-orange-700",
  その他イベント: "bg-gray-100 text-gray-700",
};

function formatEventDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ja-JP", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  });
}

function formatPostedAt(iso: string): string {
  return new Date(iso).toLocaleString("ja-JP", {
    timeZone: "Asia/Tokyo",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function EventCard({ event }: { event: Event }) {
  const categoryColor =
    CATEGORY_COLORS[event.category ?? ""] ?? CATEGORY_COLORS["その他イベント"];

  return (
    <div className="rounded-2xl border border-pink-200 bg-white shadow-sm hover:shadow-md transition-shadow overflow-hidden">
      <div className="flex flex-col md:flex-row">

        {/* 左: イベント情報（メイン） */}
        <div className="flex-1 p-5 border-b md:border-b-0 md:border-r border-pink-100">
          {/* カテゴリ + イベント日 */}
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            {event.category && (
              <span className={`text-xs font-bold px-2 py-1 rounded-full ${categoryColor}`}>
                {event.category}
              </span>
            )}
            {event.event_date && (
              <span className="text-base font-semibold text-gray-800">
                {formatEventDate(event.event_date)}
              </span>
            )}
          </div>

          {/* 会場 */}
          {event.venue && (
            <p className="text-sm text-gray-600 mb-2">
              📍 {event.venue}
            </p>
          )}

          {/* イベント日が取れない場合の投稿日表示 */}
          {!event.event_date && (
            <p className="text-xs text-gray-400 mb-2">
              投稿日: {formatPostedAt(event.posted_at)}
            </p>
          )}

          <a
            href={event.post_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block text-xs text-pink-500 hover:text-pink-700 font-medium underline"
          >
            Xで見る →
          </a>
        </div>

        {/* 右: 投稿内容（参照） */}
        <div className="w-full md:w-64 p-4 bg-gray-50 flex flex-col justify-between">
          <p className="text-xs text-gray-500 leading-relaxed whitespace-pre-wrap">
            {event.post_text.length > 180
              ? event.post_text.slice(0, 180) + "…"
              : event.post_text}
          </p>
          <p className="text-xs text-gray-400 mt-2 text-right">
            {formatPostedAt(event.posted_at)} 投稿
          </p>
        </div>
      </div>
    </div>
  );
}
