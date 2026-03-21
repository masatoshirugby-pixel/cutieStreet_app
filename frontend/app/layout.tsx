import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CUTIE_STREET_ イベント情報",
  description: "CUTIE_STREET_の公式Xアカウントからイベント告知を自動収集・表示します",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
