import { fetchEvents, type Event } from "@/lib/api";
import EventCard from "@/components/EventCard";

export const revalidate = 3600;

export default async function CandyTunePage() {
  let events: Event[] = [];
  let error = "";

  try {
    events = await fetchEvents("CANDY_TUNE_");
  } catch {
    error = "イベント情報の取得に失敗しました。しばらく経ってから再度お試しください。";
  }

  return (
    <main className="min-h-screen bg-yellow-50">
      <header className="bg-white border-b border-yellow-200 py-6 px-4 text-center">
        <h1 className="text-2xl font-bold text-yellow-600 tracking-wide">🍬 CANDY TUNE イベント情報</h1>
        <p className="text-sm text-gray-500 mt-1">公式Xのイベント告知を自動でまとめています</p>
        <nav className="mt-3 flex justify-center gap-4 text-sm">
          <a href="/" className="text-gray-400 hover:text-pink-500">CUTIE_STREET_</a>
          <span className="font-bold text-yellow-600 border-b-2 border-yellow-400 pb-1">CANDY TUNE</span>
          <a href="/sweet-steady" className="text-gray-400 hover:text-pink-500">SWEET STEADY</a>
        </nav>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8">
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
        イベント自動整理システム
      </footer>
    </main>
  );
}
