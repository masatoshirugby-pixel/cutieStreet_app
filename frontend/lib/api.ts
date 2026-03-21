export interface Event {
  id: number;
  post_id: string;
  post_text: string;
  post_url: string;
  posted_at: string; // ISO8601 UTC
  is_event: boolean;
  category: string | null;
  created_at: string;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchEvents(limit = 30): Promise<Event[]> {
  const res = await fetch(`${BASE_URL}/events?limit=${limit}`, {
    next: { revalidate: 3600 }, // ISR: 1時間キャッシュ
  });
  if (!res.ok) {
    throw new Error(`APIエラー: ${res.status}`);
  }
  return res.json();
}
