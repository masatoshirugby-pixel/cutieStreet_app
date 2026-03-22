"use client";

import { useState } from "react";
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
  return new Date(iso + "T00:00:00").toLocaleDateString("ja-JP", {
    timeZone: "Asia/Tokyo",
    month: "numeric",
    day: "numeric",
    weekday: "short",
  });
}

interface Props {
  emails: EmailItem[];
  accentColor: string;
}

export default function EmailPanel({ emails, accentColor }: Props) {
  const [open, setOpen] = useState(false);

  if (emails.length === 0) return null;

  const withDeadline = emails.filter((e) => e.deadline_date);

  return (
    <div className="relative inline-block">
      {/* バッジボタン */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-white border border-${accentColor}-300 text-${accentColor}-700 shadow-sm hover:shadow-md transition-shadow`}
      >
        📧
        <span>メール</span>
        <span className={`bg-${accentColor}-500 text-white rounded-full px-1.5 py-0.5 text-xs`}>
          {emails.length}
        </span>
        {withDeadline.length > 0 && (
          <span className="bg-red-500 text-white rounded-full px-1.5 py-0.5 text-xs">
            締切 {withDeadline.length}
          </span>
        )}
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>

      {/* ドロップダウン */}
      {open && (
        <div className="absolute right-0 top-9 z-50 w-80 rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden">
          <ul className="divide-y divide-gray-100 max-h-72 overflow-y-auto">
            {emails.map((mail) => (
              <li key={mail.id} className="px-3 py-2.5">
                <p className="text-xs font-medium text-gray-800 truncate">
                  {mail.subject ?? "(件名なし)"}
                </p>
                <div className="flex items-center justify-between mt-0.5">
                  <p className="text-xs text-gray-400">
                    {formatReceivedAt(mail.received_at)}
                  </p>
                  {mail.deadline_date && (
                    <span className="text-xs font-bold text-red-500 bg-red-50 px-1.5 py-0.5 rounded-full">
                      締切 {formatDeadline(mail.deadline_date)}
                    </span>
                  )}
                </div>
                {mail.body_preview && (
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                    {mail.body_preview}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
