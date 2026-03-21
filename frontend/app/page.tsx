import { fetchEvents } from "@/lib/api";
import EventCard from "@/components/EventCard";

export const revalidate = 3600; // ISR: 1時間ごとに再生成

export default async function EventsPage() {
  let events = [];
  let error = "";

  try {
    events = await fetchEvents(30);
  } catch (e) {
    error = "イベント情報の取得に失敗しました。しばらく経ってから再度お試しください。";
  }

  return (
    <main className="min-h-screen bg-pink-50">
      <header className="bg-white border-b border-pink-200 py-6 px-4 text-center">
        <h1 className="text-2xl font-bold text-pink-600 tracking-wide">
          🎤 CUTIE_STREET_ イベント情報
        </h1>
        <p className="text-sm text-gray-500 mt-1">公式Xのイベント告知を自動でまとめています</p>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-8">
        {error ? (
          <p className="text-center text-red-500">{error}</p>
        ) : events.length === 0 ? (
          <p className="text-center text-gray-400">現在表示できるイベント情報はありません</p>
        ) : (
          <div className="flex flex-col gap-4">
            {events.map((event) => (
              <EventCard key={event.post_id} event={event} />
            ))}
          </div>
        )}
      </div>

      <footer className="text-center text-xs text-gray-400 pb-8">
        CUTIE_STREET_ イベント自動整理システム
      </footer>
    </main>
  );
}
