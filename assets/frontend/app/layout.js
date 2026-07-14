import "./globals.css";

export const metadata = {
  title: "Crypto Trading Advisor",
  description: "Ask a Groq + LangChain agent for a BUY/SELL/HOLD opinion on any crypto.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-white dark:bg-neutral-950 text-neutral-900 dark:text-neutral-50">
        {children}
      </body>
    </html>
  );
}
