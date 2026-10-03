import { useState } from "react";
import { NavTabs, type Tab } from "./components/NavTabs";
import { Home } from "./pages/Home";
import { Chat } from "./pages/Chat";
import { Reports } from "./pages/Reports";
import { Work } from "./pages/Work";
import { Settings } from "./pages/Settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("home");
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);

  const askFromElsewhere = (text: string) => {
    setPendingMessage(text);
    setTab("ask");
  };

  return (
    <div className="min-h-screen px-4 py-8 sm:px-8">
      <div className="max-w-2xl mx-auto">
        <NavTabs active={tab} onChange={setTab} />
        <main>
          {tab === "home" && <Home onNavigate={setTab} onAsk={askFromElsewhere} />}
          {tab === "ask" && <Chat pendingMessage={pendingMessage} onConsumed={() => setPendingMessage(null)} />}
          {tab === "documents" && <Reports />}
          {tab === "work" && <Work />}
          {tab === "settings" && <Settings />}
        </main>
      </div>
    </div>
  );
}
