import { EmailItem } from "@/lib/api";

function formatReceivedAt(iso: string) {
  return new Date(iso).toLocaleString("ja-JP", {
    timeZone: "Asia/Tokyo",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDeadline(iso: string) {
  return new Date(iso).toLocaleDateString("ja-JP", {
    timeZone: "Asia/Tokyo",
    month: "long",
    day: "numeric",
    weekday: "short",
  });
}

interface Props {
  emails: EmailItem[];
  accentColor: string;
}

export default function EmailPanel({ emails, accentColor }: Props) {
  if (emails.length === 0) return null;

  const borderClass = `border-${accentColor}-200`;
  const badgeClass = `bg-${accentColor}-500 text-white`;
  const deadlineClass = `text-${accentColor}-600`;

  return (
    <div className={`mb-6 rounded-2xl border ${borderClass} bg-white shadow-sm overflow-hidden`}>
      {/* ヘッダー */}
      <div className={`px-4 py-3 bg-${accentColor}-50 border-b ${borderClass} flex items-center gap-2`}>
        <span className="text-sm font-semibold text-gray-700">📧 関連メール</span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badgeClass}`}>
          {emails.length}件
        </span>
      </div>

      {/* メール一覧 */}
      <ul className="divide-y divide-gray-100">
        {emails.map((mail) => (
          <li key={mail.id} className="px-4 py-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">
                  {mail.subject ?? "(件名なし)"}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {mail.sender ?? ""} · {formatReceivedAt(mail.received_at)}
                </p>
                {mail.body_preview && (
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                    {mail.body_preview}
                  </p>
                )}
              </div>
              {mail.deadline_date && (
                <div className="shrink-0 text-right">
                  <span className="text-xs font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded-full whitespace-nowrap">
                    締切 {formatDeadline(mail.deadline_date)}
                  </span>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
