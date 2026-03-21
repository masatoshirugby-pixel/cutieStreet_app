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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ja-JP", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function EventCard({ event }: { event: Event }) {
  const categoryColor =
    event.category ? (CATEGORY_COLORS[event.category] ?? CATEGORY_COLORS["その他イベント"]) : "";

  return (
    <div className="rounded-2xl border border-pink-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-500">{formatDate(event.posted_at)}</span>
        {event.category && (
          <span className={`text-xs font-semibold px-2 py-1 rounded-full ${categoryColor}`}>
            {event.category}
          </span>
        )}
      </div>

      <p className="text-gray-800 text-sm leading-relaxed whitespace-pre-wrap mb-4">
        {event.post_text.length > 200
          ? event.post_text.slice(0, 200) + "…"
          : event.post_text}
      </p>

      <a
        href={event.post_url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block text-xs text-pink-500 hover:text-pink-700 font-medium underline"
      >
        Xで見る →
      </a>
    </div>
  );
}
