import "./globals.css";

export const metadata = {
  title: "Crypto Trading Advisor",
  description: "Ask a Groq + LangChain agent for a BUY/SELL/HOLD opinion on any crypto.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
