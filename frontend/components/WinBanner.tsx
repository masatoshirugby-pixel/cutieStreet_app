"use client";

import { useState } from "react";
import { EmailItem } from "@/lib/api";

const WIN_KEYWORDS = ["当選", "抽選結果"];

function isWinEmail(email: EmailItem): boolean {
  return WIN_KEYWORDS.some((kw) => email.subject?.includes(kw));
}

interface Props {
  emails: EmailItem[];
}

export default function WinBanner({ emails }: Props) {
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());

  const winEmails = emails.filter((e) => isWinEmail(e) && !dismissed.has(e.id));

  if (winEmails.length === 0) return null;

  return (
    <div className="mb-4 flex flex-col gap-2">
      {winEmails.map((mail) => {
        const gmailUrl = `https://mail.google.com/mail/u/0/#search/${encodeURIComponent(
          `subject:"${mail.subject ?? ""}"`
        )}`;
        return (
          <div
            key={mail.id}
            className="flex items-start gap-3 bg-yellow-50 border-2 border-yellow-400 rounded-xl px-4 py-3 shadow"
          >
            <span className="text-2xl flex-shrink-0">🎉</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-yellow-900">
                {mail.subject ?? "(件名なし)"}
              </p>
              {mail.body_preview && (
                <p className="text-xs text-yellow-800 mt-0.5 line-clamp-2">
                  {mail.body_preview}
                </p>
              )}
              <a
                href={gmailUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block mt-1 text-xs text-blue-500 hover:text-blue-700 underline"
              >
                📧 Gmailで確認 →
              </a>
            </div>
            <button
              onClick={() => setDismissed((s) => new Set(s).add(mail.id))}
              className="text-yellow-400 hover:text-yellow-600 text-xl leading-none flex-shrink-0"
              aria-label="閉じる"
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}
