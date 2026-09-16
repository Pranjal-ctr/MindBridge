import { useState } from "react";
import HomePage from "./pages/HomePage";
import JournalPage from "./pages/JournalPage";
import GrowthPage from "./pages/GrowthPage";

export default function App() {
  const [page, setPage] = useState("home");

  const navigate = (target: string) => {
    setPage(target);
  };

  if (page === "journal") {
    return <JournalPage onNavigate={navigate} />;
  }
  if (page === "growth") {
    return <GrowthPage onNavigate={navigate} />;
  }
  return <HomePage onNavigate={navigate} />;
}
