import Image from "next/image";
import { fetchEvents, fetchEmails, type Event } from "@/lib/api";
import Calendar from "@/components/Calendar";
import EmailPanel from "@/components/EmailPanel";

export const revalidate = 3600;

const HEADER_IMAGE = "https://d1rjcmiyngzjnh.cloudfront.net/prod/public/fcopen/contents/top_image/1351/04577a8885337b8a2e8f67cc65286da1.jpeg";

export default async function CutieStreetPage() {
  let events: Event[] = [];
  let error = "";
  try {
    events = await fetchEvents("CUTIE_STREET_");
  } catch {
    error = "イベント情報の取得に失敗しました。";
  }
  const emails = await fetchEmails("CUTIE_STREET_");

  return (
    <main className="min-h-screen bg-pink-50">
      {/* ヘッダー画像 */}
      <div className="relative w-full h-48 md:h-64 overflow-hidden">
        <Image src={HEADER_IMAGE} alt="CUTIE STREET" fill className="object-cover object-top" />
        <div className="absolute inset-0 bg-black/30 flex items-end px-6 pb-4">
          <h1 className="text-white text-2xl font-bold tracking-wide drop-shadow">🎤 CUTIE_STREET_ イベント情報</h1>
        </div>
      </div>

      {/* ナビ */}
      <nav className="bg-white border-b border-pink-200 px-4 py-2 flex justify-center gap-6 text-sm">
        <span className="font-bold text-pink-600 border-b-2 border-pink-400 pb-1">CUTIE_STREET_</span>
        <a href="/candy-tune" className="text-gray-400 hover:text-pink-500 pb-1">CANDY TUNE</a>
        <a href="/sweet-steady" className="text-gray-400 hover:text-pink-500 pb-1">SWEET STEADY</a>
      </nav>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <EmailPanel emails={emails} accentColor="pink" />
        {error ? (
          <p className="text-center text-red-500">{error}</p>
        ) : (
          <Calendar events={events} accentColor="pink" />
        )}
      </div>

      <footer className="text-center text-xs text-gray-400 pb-8">イベント自動整理システム</footer>
    </main>
  );
}
