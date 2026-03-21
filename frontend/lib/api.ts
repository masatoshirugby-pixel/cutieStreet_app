export interface Event {
  id: number;
  post_id: string;
  post_text: string;
  post_url: string;
  posted_at: string;
  is_event: boolean;
  account: string;
  category: string | null;
  event_date: string | null;
  venue: string | null;
  image_url: string | null;
  created_at: string;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchEvents(account: string, limit = 200): Promise<Event[]> {
  const res = await fetch(
    `${BASE_URL}/events?account=${account}&limit=${limit}`,
    { next: { revalidate: 3600 } }
  );
  if (!res.ok) throw new Error(`APIエラー: ${res.status}`);
  return res.json();
}
