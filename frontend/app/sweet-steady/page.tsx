import Image from "next/image";
import { fetchEvents, fetchEmails, type Event } from "@/lib/api";
import Calendar from "@/components/Calendar";
import EmailPanel from "@/components/EmailPanel";

export const revalidate = 3600;

const HEADER_IMAGE = "https://d1rjcmiyngzjnh.cloudfront.net/prod/public/fcopen/contents/top_image/1217/82eb2c3a913dd9c6b552ea68418be46c.jpeg";

export default async function SweetSteadyPage() {
  let events: Event[] = [];
  let error = "";
  try {
    events = await fetchEvents("SWEET_STEADY");
  } catch {
    error = "イベント情報の取得に失敗しました。";
  }
  const emails = await fetchEmails("SWEET_STEADY");

  return (
    <main className="min-h-screen bg-blue-50">
      <div className="relative w-full h-48 md:h-64 overflow-hidden">
        <Image src={HEADER_IMAGE} alt="SWEET STEADY" fill className="object-cover object-top" />
        <div className="absolute inset-0 bg-black/30 flex items-end px-6 pb-4">
          <h1 className="text-white text-2xl font-bold tracking-wide drop-shadow">🎵 SWEET STEADY イベント情報</h1>
        </div>
      </div>

      <nav className="bg-white border-b border-blue-200 px-4 py-2 flex justify-center gap-6 text-sm">
        <a href="/" className="text-gray-400 hover:text-pink-500 pb-1">CUTIE_STREET_</a>
        <a href="/candy-tune" className="text-gray-400 hover:text-pink-500 pb-1">CANDY TUNE</a>
        <span className="font-bold text-blue-600 border-b-2 border-blue-400 pb-1">SWEET STEADY</span>
      </nav>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex justify-end mb-3">
          <EmailPanel emails={emails} accentColor="blue" />
        </div>
        {error ? (
          <p className="text-center text-red-500">{error}</p>
        ) : (
          <Calendar events={events} accentColor="blue" />
        )}
      </div>

      <footer className="text-center text-xs text-gray-400 pb-8">イベント自動整理システム</footer>
    </main>
  );
}
