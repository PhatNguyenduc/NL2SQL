import React, { useState, useEffect, useRef } from "react";
import { api, ChatResponse, QueryExecutionResponse } from "./api/client";
import { Analytics } from "./components/Analytics";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
  timestamp: Date;
}

const STORAGE_KEY = "nl2sql_conversation";
const SESSION_KEY = "nl2sql_session_id";
const QUERIES_COUNT_KEY = "nl2sql_total_queries";

// Load conversation from localStorage
const loadConversation = (): ChatMessage[] => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      // Convert timestamp strings back to Date objects
      return parsed.map((msg: any) => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
        response: msg.response || undefined,
      }));
    }
  } catch (err) {
    console.error("Failed to load conversation:", err);
  }
  return [];
};

// Save conversation to localStorage
const saveConversation = (messages: ChatMessage[]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  } catch (err) {
    console.error("Failed to save conversation:", err);
  }
};

// Load session ID from localStorage or create new one
const loadOrCreateSessionId = (): string => {
  try {
    const stored = localStorage.getItem(SESSION_KEY);
    if (stored) {
      return stored;
    }
  } catch (err) {
    console.error("Failed to load session ID:", err);
  }
  const newSessionId = `session-${Date.now()}`;
  try {
    localStorage.setItem(SESSION_KEY, newSessionId);
  } catch (err) {
    console.error("Failed to save session ID:", err);
  }
  return newSessionId;
};

// Load total queries count
const loadTotalQueries = (): number => {
  try {
    const stored = localStorage.getItem(QUERIES_COUNT_KEY);
    if (stored) {
      return parseInt(stored, 10) || 0;
    }
  } catch (err) {
    console.error("Failed to load total queries:", err);
  }
  return 0;
};

// Save total queries count
const saveTotalQueries = (count: number) => {
  try {
    localStorage.setItem(QUERIES_COUNT_KEY, count.toString());
  } catch (err) {
    console.error("Failed to save total queries:", err);
  }
};

export const Home: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<"chat" | "analytics">("chat");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadConversation());
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => loadOrCreateSessionId());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isSubmittingRef = useRef(false);
  const [totalQueries, setTotalQueries] = useState<number>(() => loadTotalQueries());
  const [temperature, setTemperature] = useState<number>(0.1);
  const [autoExecute, setAutoExecute] = useState<boolean>(true);
  const [apiHealth, setApiHealth] = useState<any>(null);
  const [showApiInfo, setShowApiInfo] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [tableSearch, setTableSearch] = useState<{ [key: string]: string }>({});
  const [zoomedTable, setZoomedTable] = useState<QueryExecutionResponse | null>(null);
  const [searchPopup, setSearchPopup] = useState<{ tableId: string; isOpen: boolean; position?: { top: number; left: number } }>({ tableId: "", isOpen: false });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  // Close zoom modal and search popup on ESC key
  useEffect(() => {
    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (zoomedTable) {
          setZoomedTable(null);
        }
        if (searchPopup.isOpen) {
          setSearchPopup({ tableId: "", isOpen: false });
        }
      }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [zoomedTable, searchPopup.isOpen]);

  // Global mouse move handler for dragging
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      e.preventDefault();
      const newPosition = {
        top: Math.max(0, Math.min(e.clientY - dragOffset.y, window.innerHeight - 200)),
        left: Math.max(0, Math.min(e.clientX - dragOffset.x, window.innerWidth - 256)),
      };
      setSearchPopup((prev) => {
        if (!prev.position) return prev;
        return {
          ...prev,
          position: newPosition,
        };
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener("mousemove", handleMouseMove, { passive: false });
    document.addEventListener("mouseup", handleMouseUp);
    
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, dragOffset]);

  // Auto scroll to bottom when new message is added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Save conversation to localStorage whenever messages change
  useEffect(() => {
    if (messages.length > 0) {
      saveConversation(messages);
    }
  }, [messages]);

  // Save total queries to localStorage whenever it changes
  useEffect(() => {
    if (totalQueries > 0) {
      saveTotalQueries(totalQueries);
    }
  }, [totalQueries]);

  // Check API health on mount and periodically
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await api.getHealth();
        setApiHealth(health);
      } catch (err) {
        setApiHealth({ status: "error", error: "Failed to connect" });
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim() || loading || isSubmittingRef.current) return;

    // Prevent double submission
    isSubmittingRef.current = true;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setError(null);
    setQuery(""); // Clear input immediately

    try {
      const response = await api.chat({
        message: userMessage.content,
        session_id: sessionId,
        execute_query: autoExecute,
        temperature: temperature,
      });

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: userMessage.content, // Keep reference to original query
        response: response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      
      // Update total queries count for Analytics badge
      setTotalQueries((prev) => prev + 1);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to generate SQL");
      console.error("API Error:", err);
      
      // Add error message to chat
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: userMessage.content,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
      isSubmittingRef.current = false;
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleClearChat = () => {
    if (window.confirm("Are you sure you want to clear all conversation history?")) {
      setMessages([]);
      setTotalQueries(0);
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(QUERIES_COUNT_KEY);
      // Keep session ID for continuity
    }
  };

  const downloadCSV = async (execution: QueryExecutionResponse) => {
    if (!execution.rows || execution.rows.length === 0) return;

    const columns = execution.columns || Object.keys(execution.rows[0] || {});
    const headers = columns.join(",");
    const rows = execution.rows.map((row) =>
      columns.map((col) => {
        const value = String(row[col] ?? "");
        // Escape commas and quotes in CSV
        if (value.includes(",") || value.includes('"') || value.includes("\n")) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value;
      }).join(",")
    );

    const csvContent = [headers, ...rows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const defaultFileName = `query_result_${new Date().toISOString().replace(/[:.]/g, "-")}.csv`;

    // Try to use File System Access API (allows choosing save location)
    // @ts-ignore - File System Access API types may not be available
    if ('showSaveFilePicker' in window) {
      try {
        // @ts-ignore
        const fileHandle = await window.showSaveFilePicker({
          suggestedName: defaultFileName,
          types: [{
            description: 'CSV files',
            accept: {
              'text/csv': ['.csv'],
            },
          }],
        });

        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();
        return;
      } catch (err: any) {
        // User cancelled or error occurred, fall back to default download
        if (err.name !== 'AbortError') {
          console.warn('File System Access API failed, using fallback:', err);
        } else {
          // User cancelled, don't download
          return;
        }
      }
    }

    // Fallback: Use traditional download (browser will use default download location)
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", defaultFileName);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const escapeRegex = (str: string) => {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  };

  const highlightText = (text: string, searchTerm: string) => {
    if (!searchTerm || searchTerm.trim().length === 0) {
      return <>{text}</>;
    }
    
    const trimmedTerm = searchTerm.trim();
    const escapedTerm = escapeRegex(trimmedTerm);
    
    try {
      const parts = text.split(new RegExp(`(${escapedTerm})`, 'gi'));
      return (
        <>
          {parts.map((part, i) => 
            part.toLowerCase() === trimmedTerm.toLowerCase() ? (
              <mark key={i} className="bg-green-500/30 text-green-200 rounded px-0.5">
                {part}
              </mark>
            ) : (
              part
            )
          )}
        </>
      );
    } catch (e) {
      return <>{text}</>;
    }
  };

  const renderTable = (execution: QueryExecutionResponse, tableId?: string, isZoomed: boolean = false) => {
    if (!execution.rows || execution.rows.length === 0) {
      return (
        <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
          No data returned
        </div>
      );
    }

    const columns = execution.columns || Object.keys(execution.rows[0] || {});
    
    // Get search term with strict checking
    let searchTerm = "";
    if (tableId && tableId in tableSearch && tableSearch[tableId]) {
      const raw = String(tableSearch[tableId]).trim();
      searchTerm = raw.toLowerCase();
    }

    return (
      <div className={isZoomed ? "h-full" : "overflow-auto max-h-[400px]"}>
        <table key={`${tableId}-${searchTerm}`} className={`min-w-full ${isZoomed ? "text-sm" : "text-xs"}`}>
          <thead className="bg-[#0f1724] border-b border-gray-800 text-gray-300 sticky top-0 z-10">
            <tr>
              {columns.map((col) => (
                <Th key={col}>{col}</Th>
              ))}
            </tr>
          </thead>
          <tbody>
            {execution.rows.map((row, idx) => (
              <tr
                key={idx}
                className={idx % 2 === 0 ? "bg-[#05070c]" : "bg-[#070b12]"}
              >
                {columns.map((col) => {
                  const cellValue = String(row[col] ?? "");
                  // Only highlight if searchTerm is non-empty and matches
                  const shouldHighlight = searchTerm !== "" && searchTerm.length > 0;
                  const hasMatch = shouldHighlight && cellValue.toLowerCase().includes(searchTerm);
                  
                  return (
                    <Td key={col} highlight={hasMatch}>
                      {hasMatch && tableId && tableSearch[tableId] 
                        ? highlightText(cellValue, tableSearch[tableId]) 
                        : cellValue}
                    </Td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="h-screen bg-[#05070c] text-gray-100 flex font-sans overflow-hidden">
      {/* Show Sidebar Button (when sidebar is closed) */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed left-4 top-4 z-50 glow-btn w-8 h-8 rounded-lg flex items-center justify-center text-xs shadow-lg animate-fade-in"
          title="Show sidebar"
        >
          ▶
        </button>
      )}

      {/* Sidebar */}
      <aside
        className={`bg-[#0b1018] border-r border-gray-800 flex flex-col h-full overflow-hidden ${
          sidebarOpen 
            ? "w-64 transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)]" 
            : "w-0 transition-all duration-300 ease-[cubic-bezier(0.4,0,1,1)]"
        }`}
        style={{ 
          willChange: 'width',
          minWidth: sidebarOpen ? '16rem' : '0'
        }}
      >
        <div className={`h-16 flex items-center justify-between px-5 border-b border-gray-800 flex-shrink-0 transition-opacity whitespace-nowrap ${
          sidebarOpen 
            ? "opacity-100 duration-300 delay-200 ease-out" 
            : "opacity-0 duration-150 delay-0 ease-in"
        }`}>
          <div className="flex items-center min-w-0 overflow-hidden">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-sky-400 flex items-center justify-center text-xs font-semibold flex-shrink-0">
              NL
            </div>
            <div className="ml-3 overflow-hidden">
              <div className="text-sm font-semibold truncate">NL2SQL Assistant</div>
              <div className="text-[11px] text-gray-400 truncate">Natural language → SQL</div>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="glow-btn w-7 h-7 rounded-lg flex items-center justify-center text-xs"
            title="Hide sidebar"
          >
            ◀
          </button>
        </div>

        <nav className={`flex-1 py-4 overflow-y-auto min-h-0 text-[15px] leading-relaxed transition-opacity ${
          sidebarOpen 
            ? "opacity-100 duration-300 delay-200 ease-out" 
            : "opacity-0 duration-150 delay-0 ease-in"
        }`}>
          <NavItem
            active={currentPage === "chat"}
            onClick={() => setCurrentPage("chat")}
            icon="💬"
            label="Chat"
          />
          <NavItem
            active={currentPage === "analytics"}
            onClick={() => setCurrentPage("analytics")}
            icon="📊"
            label="Analytics"
            badge={totalQueries > 0 ? totalQueries : undefined}
          />

          {/* Settings Section */}
          <div className="border-t border-gray-800 mt-4 pt-4 space-y-3 px-2">
            <div className="text-xl font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center space-x-2">
              <span className="text-lg">⚙️</span>
              <span className="text-2xl">Settings</span>
            </div>

            {/* API Status */}
            <div className="bg-[#0f1724] border border-gray-700/50 rounded-xl p-3">
              <div className="text-sm font-semibold text-gray-200 mb-2 flex items-center space-x-2">
                <span className="text-lg">🔌</span>
                <span>API Status</span>
              </div>
              {apiHealth?.status === "healthy" ? (
                <div className="text-sm text-green-400">✅ Connected</div>
              ) : (
                <div className="text-sm text-red-400">
                  ❌ {apiHealth?.error || "Disconnected"}
                </div>
              )}
            </div>

            {/* API Info */}
            <div className="bg-[#0f1724] border border-gray-700/50 rounded-xl p-3">
              <button
                onClick={() => setShowApiInfo(!showApiInfo)}
                className="w-full text-sm font-semibold text-gray-200 flex items-center space-x-2"
              >
                <span className="text-lg">📊</span>
                <span>API Info</span>
                <span className={`ml-auto transition-transform duration-300 ${showApiInfo ? "rotate-90" : "rotate-0"}`}>
                  ▶
                </span>
              </button>
              <div 
                className={`overflow-hidden transition-all duration-300 ease-in-out ${
                  showApiInfo ? "max-h-40 opacity-100 mt-2" : "max-h-0 opacity-0 mt-0"
                }`}
              >
                {apiHealth?.status === "healthy" && (
                  <div className="space-y-1 text-sm text-gray-300">
                    <div>
                      <span className="text-gray-400">LLM Provider:</span>{" "}
                      <span className="text-gray-200">{apiHealth.llm_provider || "N/A"}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Model:</span>{" "}
                      <span className="text-gray-200">{apiHealth.llm_model || "N/A"}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Database:</span>{" "}
                      <span className={apiHealth.database_connected ? "text-green-400" : "text-red-400"}>
                        {apiHealth.database_connected ? "✅" : "❌"}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Tables:</span>{" "}
                      <span className="text-gray-200">{apiHealth.tables || 0}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* LLM Temperature */}
            <div className="bg-[#0f1724] border border-gray-700/50 rounded-xl p-3">
              <div className="text-sm font-semibold text-gray-200 mb-2 flex items-center space-x-2">
                <span className="text-lg">🌡️</span>
                <span>LLM Temperature</span>
              </div>
              <div className="space-y-2">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-sky-500"
                />
                <div className="flex justify-between text-xs text-gray-400">
                  <span>0.0</span>
                  <span className="text-gray-300 font-medium">{temperature.toFixed(1)}</span>
                  <span>1.0</span>
                </div>
                <div className="text-[11px] text-gray-500 italic break-words whitespace-normal leading-relaxed">
                  Lower = more deterministic, Higher = more creative
                </div>
              </div>
            </div>

            {/* SQL Execution Toggle */}
            <div className="bg-[#0f1724] border border-gray-700/50 rounded-xl p-3">
              <div className="text-sm font-semibold text-gray-200 mb-2 flex items-center space-x-2">
                <span className="text-lg">🚀</span>
                <span>Execution</span>
              </div>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoExecute}
                  onChange={(e) => setAutoExecute(e.target.checked)}
                  className="w-4 h-4 rounded bg-gray-700 border-gray-600 text-sky-500 focus:ring-sky-500 focus:ring-2 cursor-pointer"
                />
                <span className="text-sm text-gray-200">Auto-execute queries</span>
              </label>
            </div>
          </div>
        </nav>

        <div className={`border-t border-gray-800 p-4 flex items-center text-xs text-gray-400 flex-shrink-0 transition-opacity whitespace-nowrap ${
          sidebarOpen 
            ? "opacity-100 duration-300 delay-200 ease-out" 
            : "opacity-0 duration-150 delay-0 ease-in"
        }`}>
          <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center mr-2 text-sm">
            👤
          </div>
          <div className="overflow-hidden">
            <div className="text-gray-200 truncate">User profile</div>
            <div className="text-[10px] text-gray-500 truncate">Signed in</div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {currentPage === "analytics" ? (
          <Analytics />
        ) : (
          <>
            {/* Header */}
            <header className="h-16 border-b border-gray-800 flex items-center px-8">
              <h1 className="text-lg font-semibold tracking-tight">
                Natural Language to <span className="text-sky-400">SQL</span>
              </h1>
            </header>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6 min-h-0">
          {messages.length === 0 && !loading && (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm h-full">
              <div className="text-center">
                <div className="text-4xl mb-4">💬</div>
                <div>Enter a natural language query to generate SQL</div>
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className="space-y-4">
              {/* User Message */}
              {message.role === "user" && (
                <div className="flex justify-end">
                  <div className="max-w-2xl">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-xs text-gray-400">
                        {message.timestamp.toLocaleTimeString()}
                      </span>
                      <span className="text-xs text-gray-500">You</span>
                    </div>
                    <div className="bg-sky-500/20 border border-sky-500/30 rounded-2xl px-4 py-3 text-sm text-gray-100">
                      {message.content}
                    </div>
                  </div>
                </div>
              )}

              {/* Assistant Response */}
              {message.role === "assistant" && message.response && (
                <div className="flex justify-start">
                  <div className="max-w-4xl w-full space-y-4">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-xs text-gray-500">Assistant</span>
                      <span className="text-xs text-gray-400">
                        {message.timestamp.toLocaleTimeString()}
                      </span>
                    </div>

                    {/* SQL Preview */}
                    <section className="bg-[#0b1018] rounded-2xl border border-gray-800 p-5 shadow-lg">
                      <div className="flex justify-between items-center mb-4">
                        <div className="inline-flex items-center space-x-2 text-sm text-gray-300">
                          <span className="w-7 h-7 rounded-full bg-emerald-500/10 border border-emerald-500/40 flex items-center justify-center">
                            <span className="text-lg">🧠</span>
                          </span>
                          <span>Generated SQL:</span>
                          <span className="text-xs text-gray-400">
                            (Confidence: {(message.response.sql_generation.confidence * 100).toFixed(1)}%)
                          </span>
                        </div>
                        <button
                          onClick={() => copyToClipboard(message.response!.sql_generation.query)}
                          className="glow-btn text-xs px-2 py-1 rounded-md"
                        >
                          Copy SQL
                        </button>
                      </div>

                      <div className="bg-[#05070c] border border-gray-800 rounded-xl p-4 font-mono text-sm text-gray-100 shadow-inner">
                        <div className="text-xs text-gray-400 mb-2">
                          {message.response.sql_generation.tables_used.length > 0
                            ? `Tables: ${message.response.sql_generation.tables_used.join(", ")}`
                            : "SELECT query"}
                        </div>
                        <pre className="whitespace-pre-wrap leading-relaxed">
                          {message.response.sql_generation.query}
                        </pre>
                      </div>

                      {message.response.sql_generation.explanation && (
                        <div className="mt-3 text-xs text-gray-400 italic">
                          💡 {message.response.sql_generation.explanation}
                        </div>
                      )}
                    </section>

                    {/* Query Results */}
                    {message.response.execution && (
                      <section className="bg-[#0b1018] rounded-2xl border border-gray-800 p-5 shadow-lg">
                        <div className="flex justify-between items-center mb-3">
                          <h2 className="text-sm font-semibold text-gray-200">Query Results</h2>
                          {message.response.execution.success && (
                            <div className="flex items-center space-x-2">
                              <div className="text-xs text-gray-400">
                                {message.response.execution.row_count} rows •{" "}
                                {message.response.execution.execution_time.toFixed(3)}s
                              </div>
                              <div className="flex items-center space-x-1 relative">
                                <button
                                  onClick={(e) => {
                                    const tableId = `table-${message.id}`;
                                    const rect = e.currentTarget.getBoundingClientRect();
                                    setSearchPopup({ 
                                      tableId, 
                                      isOpen: true,
                                      position: {
                                        top: rect.bottom + 8,
                                        left: rect.right - 256 // 256px = w-64 (width của popup)
                                      }
                                    });
                                  }}
                                  className="glow-btn text-xs px-2 py-1 rounded-md"
                                  title="Search in table"
                                >
                                  🔍
                                </button>
                                <button
                                  onClick={() => setZoomedTable(message.response!.execution!)}
                                  className="glow-btn text-xs px-2 py-1 rounded-md"
                                  title="Zoom table"
                                >
                                  🔎
                                </button>
                                <button
                                  onClick={async () => {
                                    try {
                                      await downloadCSV(message.response!.execution!);
                                    } catch (err) {
                                      console.error("Failed to download CSV:", err);
                                    }
                                  }}
                                  className="glow-btn text-xs px-2 py-1 rounded-md"
                                  title="Download CSV"
                                >
                                  📥
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                        <div className="overflow-hidden rounded-xl border border-gray-800 bg-[#05070c]">
                          {message.response.execution.success ? (
                            renderTable(message.response.execution, `table-${message.id}`)
                          ) : (
                            <div className="flex items-center justify-center h-32 text-red-400 text-sm">
                              ❌ {message.response.execution.error_message || "Query execution failed"}
                            </div>
                          )}
                        </div>
                      </section>
                    )}
                  </div>
                </div>
              )}

              {/* Error Message */}
              {message.role === "assistant" && !message.response && error && (
                <div className="flex justify-start">
                  <div className="max-w-2xl">
                    <div className="bg-red-900/20 border border-red-800 rounded-2xl p-5 shadow-lg">
                      <div className="flex items-center space-x-2 text-red-300">
                        <span>❌</span>
                        <span className="font-semibold">Error:</span>
                        <span>{error}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Loading Indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="max-w-md">
                <div className="flex items-center space-x-2 mb-1">
                  <span className="text-xs text-gray-500">Assistant</span>
                  <span className="text-xs text-gray-400">
                    {new Date().toLocaleTimeString()}
                  </span>
                </div>
                <div className="bg-[#0b1018] border border-gray-800 rounded-2xl px-4 py-3 flex items-center space-x-2 w-fit">
                  <span className="text-sm text-sky-400">Generating SQL</span>
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></div>
                    <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></div>
                    <div className="w-2 h-2 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></div>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <section className="mt-auto px-8 pb-6 border-t border-gray-800 pt-4 flex-shrink-0">
          {messages.length > 0 && (
            <div className="flex justify-end mb-3">
              <button
                onClick={handleClearChat}
                className="glow-btn px-3 py-1.5 rounded-lg text-sm flex items-center space-x-1"
                title="Clear conversation history"
              >
                <span>🗑️</span>
                <span>Clear Chat</span>
              </button>
            </div>
          )}
          <form onSubmit={handleSubmit} className="glow-chat">
            <div className="glow-chat-inner px-4 py-3 flex items-center space-x-3">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={loading}
                className="flex-1 bg-transparent border-none outline-none text-sm text-gray-100 placeholder-gray-500 disabled:opacity-50"
                placeholder="Type your natural language query... (e.g., 'Show me all users from Vietnam')"
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="glow-btn px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Generating..." : "Generate SQL"}
              </button>
            </div>
          </form>
        </section>
          </>
        )}
      </main>

      {/* Zoomed Table Modal - Similar to Streamlit's dataframe zoom */}
      {zoomedTable && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center"
          onClick={() => setZoomedTable(null)}
        >
          <div
            className="bg-[#0b1018] w-[95vw] h-[95vh] flex flex-col border border-gray-700 rounded-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex justify-between items-center p-4 border-b border-gray-800 flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-200">Query Results</h2>
              <div className="flex items-center space-x-2 relative">
                <button
                  onClick={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setSearchPopup({ 
                      tableId: "zoomed", 
                      isOpen: true,
                      position: {
                        top: rect.bottom + 8,
                        left: rect.right - 256 // 256px = w-64 (width của popup)
                      }
                    });
                  }}
                  className="glow-btn text-xs px-3 py-1.5 rounded-md"
                  title="Search in table"
                >
                  🔍 Search
                </button>
                <button
                  onClick={async () => {
                    try {
                      await downloadCSV(zoomedTable);
                    } catch (err) {
                      console.error("Failed to download CSV:", err);
                    }
                  }}
                  className="glow-btn text-xs px-3 py-1.5 rounded-md"
                  title="Download CSV"
                >
                  📥 Download CSV
                </button>
                <button
                  onClick={() => setZoomedTable(null)}
                  className="glow-btn text-xs px-3 py-1.5 rounded-md"
                  title="Close (ESC)"
                >
                  ✕ Close
                </button>
              </div>
            </div>
            
            {/* Table Container - Full scrollable area */}
            <div className="flex-1 overflow-auto bg-[#05070c] p-4">
              {renderTable(zoomedTable, "zoomed", true)}
            </div>
          </div>
        </div>
      )}

      {/* Search Popup Modal */}
      {searchPopup.isOpen && searchPopup.position && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/20 z-40"
            onClick={() => setSearchPopup({ tableId: "", isOpen: false })}
          />
          {/* Popup */}
          <div
            className="fixed z-50 bg-[#0b1018] w-64 border border-gray-700 rounded-lg shadow-2xl select-none"
            style={{
              top: `${searchPopup.position.top}px`,
              left: `${searchPopup.position.left}px`,
              userSelect: 'none',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header - Draggable area */}
            <div 
              className="flex justify-between items-center px-3 py-2 border-b border-gray-800 cursor-grab active:cursor-grabbing"
              onMouseDown={(e) => {
                // Don't start dragging if clicking on close button
                if ((e.target as HTMLElement).closest('button')) return;
                
                const popupElement = e.currentTarget.parentElement as HTMLElement;
                if (popupElement) {
                  const popupRect = popupElement.getBoundingClientRect();
                  setIsDragging(true);
                  setDragOffset({
                    x: e.clientX - popupRect.left,
                    y: e.clientY - popupRect.top,
                  });
                  e.preventDefault();
                }
              }}
            >
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-1.5">
                <span className="text-xs">🔍</span>
                <span>Search</span>
              </h3>
              <button
                onClick={() => setSearchPopup({ tableId: "", isOpen: false })}
                className="text-gray-400 hover:text-gray-200 text-lg font-bold w-5 h-5 flex items-center justify-center rounded hover:bg-gray-800 transition-colors leading-none"
                title="Close (ESC)"
                onMouseDown={(e) => e.stopPropagation()}
              >
                ×
              </button>
            </div>
            
            {/* Search Input */}
            <div className="p-3">
              <input
                type="text"
                autoFocus
                value={searchPopup.tableId && tableSearch[searchPopup.tableId] !== undefined ? tableSearch[searchPopup.tableId] : ""}
                onChange={(e) => {
                  if (searchPopup.tableId) {
                    const newValue = e.target.value;
                    setTableSearch((prev) => ({
                      ...prev,
                      [searchPopup.tableId]: newValue
                    }));
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === "Escape") {
                    setSearchPopup({ tableId: "", isOpen: false });
                  }
                }}
                placeholder="Search in table..."
                className="w-full bg-[#05070c] border border-gray-700 rounded-md px-3 py-2 text-xs text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
              />
              <div className="mt-2 flex items-center justify-end">
                <button
                  onClick={() => {
                    // Close popup immediately
                    setSearchPopup({ tableId: "", isOpen: false });
                    // Clear the search term
                    if (searchPopup.tableId) {
                      setTableSearch((prev) => {
                        const newState = { ...prev };
                        delete newState[searchPopup.tableId];
                        return newState;
                      });
                    }
                  }}
                  className="text-[10px] text-gray-400 hover:text-gray-200 underline"
                >
                  Clear
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

type NavItemProps = {
  icon: string;
  label: string;
  active?: boolean;
  onClick?: () => void;
  badge?: number;
};

const NavItem: React.FC<NavItemProps> = ({ icon, label, active, onClick, badge }) => {
  return (
    <button
      onClick={onClick}
      className={`nav-item-animated w-full flex items-center justify-between px-5 py-3 text-[15px] font-medium transition-colors whitespace-nowrap ${
        active
          ? "bg-[#111827] text-sky-300 border-l-2 border-sky-500 nav-item-active"
          : "text-gray-200 hover:text-white hover:bg-[#121826]"
      }`}
    >
      <div className="flex items-center space-x-3 overflow-hidden flex-shrink-0">
        <span className="text-xl flex-shrink-0">{icon}</span>
        <span className="truncate">{label}</span>
      </div>
      {badge !== undefined && badge > 0 && (
        <span className="min-w-[22px] h-[22px] px-1 rounded-full bg-red-500 text-[11px] flex items-center justify-center text-white font-semibold flex-shrink-0">
          {badge}
        </span>
      )}
    </button>
  );
};

type CellProps = {
  children: React.ReactNode;
  highlight?: boolean;
};

const Th: React.FC<CellProps> = ({ children }) => (
  <th className="text-left px-4 py-2 font-medium text-[11px] uppercase tracking-wide">
    {children}
  </th>
);

const Td: React.FC<CellProps> = ({ children, highlight }) => (
  <td className={`px-4 py-2 text-[13px] text-gray-200 border-t border-gray-800/60 transition-colors duration-200 ${
    highlight ? "bg-green-500/10" : ""
  }`}>
    {children}
  </td>
);

export default Home;
