export interface EmailItem {
  id: number;
  message_id: string;
  account: string;
  subject: string | null;
  sender: string | null;
  received_at: string;
  body_preview: string | null;
  deadline_date: string | null;
  created_at: string;
}

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
  source: string;
  created_at: string;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchEvents(account: string, limit = 1000): Promise<Event[]> {
  const res = await fetch(
    `${BASE_URL}/events?account=${account}&limit=${limit}`,
    { next: { revalidate: 300 } }
  );
  if (!res.ok) throw new Error(`APIエラー: ${res.status}`);
  return res.json();
}

export async function fetchEmails(account: string): Promise<EmailItem[]> {
  const res = await fetch(
    `${BASE_URL}/emails?account=${account}`,
    { next: { revalidate: 300 } }
  );
  if (!res.ok) return [];
  return res.json();
}
