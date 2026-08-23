'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Loader2, Copy, Download, Terminal, Layers, Zap, AlertCircle, MessageSquare, Monitor, Settings, LogOut, RefreshCw, ExternalLink, Check } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  agent?: string;
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

interface AgentActivity {
  id: string;
  agent: string;
  status: 'running' | 'complete' | 'error';
  message: string;
  timestamp: Date;
}

type Phase = 'planning' | 'coding' | 'testing' | 'deploying' | 'complete' | 'error';
type AuthState = 'checking' | 'signed_out' | 'signed_in';
// EM-6: the four states every job view must render.
type JobState = 'empty' | 'loading' | 'error' | 'complete';

const TOKEN_KEY = 'emergent_token';

const ROLE_TO_PHASE: Record<string, Phase> = {
  planner: 'planning',
  designer: 'planning',
  frontend: 'coding',
  backend: 'coding',
  integration: 'coding',
  qa: 'testing',
  devops: 'deploying',
};

function authHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function WorkspacePage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      agent: 'Orchestrator',
      content: 'Welcome to Emergent! I\'m your Orchestrator agent. Describe the app you want to build, and my team will plan, code, test, and deploy it for you.',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activities, setActivities] = useState<AgentActivity[]>([]);
  const [currentPhase, setCurrentPhase] = useState<Phase>('planning');
  const [previewUrl, setPreviewUrl] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [mounted, setMounted] = useState(false);
  const [credits, setCredits] = useState<number | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState<JobState>('empty');
  const [jobError, setJobError] = useState<string>('');

  // EM-6: auth state + previously dead controls are now wired.
  const [authState, setAuthState] = useState<AuthState>('checking');
  const [token, setToken] = useState<string | null>(null);
  const [authUsername, setAuthUsername] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [copied, setCopied] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);

  const loadCredits = useCallback(async (t: string) => {
    try {
      const res = await fetch('/api/pipeline/credits', { headers: authHeaders(t) });
      if (res.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setAuthState('signed_out');
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setCredits(data.credits);
      }
    } catch (err) {
      console.error('Failed to fetch credits', err);
    }
  }, []);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) {
      setToken(stored);
      setAuthState('signed_in');
      loadCredits(stored);
    } else {
      setAuthState('signed_out');
    }
  }, [loadCredits]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const pushSystem = (content: string) => {
    setMessages(prev => [...prev, {
      id: Date.now().toString() + Math.random(),
      role: 'system',
      content,
      timestamp: new Date(),
    }]);
  };

  const signOut = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setCredits(null);
    setAuthState('signed_out');
    setShowSettings(false);
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authUsername.trim() || !authPassword || authBusy) return;
    setAuthBusy(true);
    setAuthError('');
    try {
      const body = new URLSearchParams({ username: authUsername, password: authPassword });
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Sign-in failed (${res.status})`);
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      setAuthState('signed_in');
      setAuthPassword('');
      loadCredits(data.access_token);
    } catch (err: any) {
      setAuthError(err.message || 'Sign-in failed');
    } finally {
      setAuthBusy(false);
    }
  };

  const handleRegister = async () => {
    if (!authUsername.trim() || !authPassword || authBusy) return;
    setAuthBusy(true);
    setAuthError('');
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: `${authUsername.toLowerCase()}@example.com`,
          username: authUsername,
          password: authPassword,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Registration failed (${res.status})`);
      }
      // Registration succeeded — now sign in with the same credentials.
      const body = new URLSearchParams({ username: authUsername, password: authPassword });
      const loginRes = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      if (!loginRes.ok) throw new Error('Registered, but sign-in failed. Try signing in.');
      const data = await loginRes.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      setAuthState('signed_in');
      setAuthPassword('');
      loadCredits(data.access_token);
    } catch (err: any) {
      setAuthError(err.message || 'Registration failed');
    } finally {
      setAuthBusy(false);
    }
  };

  // EM-6: EventSource cannot carry an Authorization header, so the SSE
  // stream is consumed with fetch + ReadableStream instead.
  const streamJob = useCallback(async (jobId: string, t: string) => {
    try {
      const res = await fetch(`/api/pipeline/stream/${jobId}`, { headers: authHeaders(t) });
      if (!res.ok || !res.body) {
        throw new Error(`Stream unavailable (${res.status})`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let payload: any;
          try { payload = JSON.parse(line.slice(6)); } catch { continue; }
          handleStreamEvent(payload, jobId);
        }
      }
    } catch (err: any) {
      setIsLoading(false);
      let status: any = null;
      for (let attempt = 0; attempt < 10; attempt += 1) {
        try {
          const statusRes = await fetch(`/api/pipeline/status/${jobId}`, { headers: authHeaders(t) });
          if (statusRes.ok) {
            status = await statusRes.json();
            if (status.status === 'complete' || status.status === 'failed') break;
          }
        } catch {
          // A temporary network failure is handled by the next bounded poll.
        }
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      if (status?.status === 'complete') {
        setJobState('complete');
        setCurrentPhase('complete');
        setPreviewUrl(status.preview_url || `/preview/${jobId}/`);
        pushSystem('Build completed while the live progress stream was reconnecting.');
      } else if (status?.status === 'failed') {
        setJobState('error');
        setCurrentPhase('error');
        setJobError(status.errors?.at(-1) || 'Pipeline failed');
        pushSystem(`Pipeline failed: ${status.errors?.at(-1) || 'unknown error'}`);
      } else {
        setJobState('loading');
        setJobError('Progress connection interrupted; the build is still running. Refresh status to continue.');
        pushSystem(`Progress stream interrupted: ${err.message || 'connection lost'}`);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleStreamEvent = (payload: any, jobId: string) => {
    if (payload.event === 'agent_start' || payload.event === 'agent_done') {
      const running = payload.event === 'agent_start';
      const agentName = payload.agent || payload.role;
      setActivities(prev => [...prev, {
        id: Date.now().toString() + Math.random(),
        agent: agentName,
        status: running ? 'running' : 'complete',
        message: `${agentName} is ${running ? 'running' : 'complete'}...`,
        timestamp: new Date(),
      }]);
      const phase = ROLE_TO_PHASE[agentName];
      if (phase) setCurrentPhase(phase);
    } else if (payload.event === 'agent_error') {
      setActivities(prev => [...prev, {
        id: Date.now().toString() + Math.random(),
        agent: payload.role || 'agent',
        status: 'error',
        message: payload.data?.error || 'agent failed',
        timestamp: new Date(),
      }]);
    } else if (payload.event === 'pipeline_error') {
      setIsLoading(false);
      setCurrentPhase('error');
      setJobState('error');
      setJobError(payload.data?.error || 'Pipeline failed');
      pushSystem(`Pipeline failed: ${payload.data?.error}`);
    } else if (payload.event === 'pipeline_complete') {
      setIsLoading(false);
      const failed = payload.data?.status && payload.data.status !== 'complete';
      if (failed) {
        setCurrentPhase('error');
        setJobState('error');
        const errs: string[] = payload.data?.errors || [];
        setJobError(errs[errs.length - 1] || 'Pipeline did not complete');
        pushSystem(`Pipeline failed: ${errs[errs.length - 1] || 'unknown error'}`);
      } else {
        setCurrentPhase('complete');
        setJobState('complete');
        setPreviewUrl(`/preview/${jobId}/`);
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          agent: 'Orchestrator',
          content: `I've completed building your app! The multi-agent team has finished all phases. You can now preview the live app, iterate with more instructions, or export the code.`,
          timestamp: new Date(),
          metadata: { jobId },
        }]);
      }
      if (token) loadCredits(token);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || !token) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setJobState('loading');
    setJobError('');
    setActivities([]);
    setCurrentPhase('planning');

    try {
      const res = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
        body: JSON.stringify({ prompt: input }),
      });

      if (res.status === 401) {
        signOut();
        throw new Error('Session expired — please sign in again.');
      }
      if (res.status === 402) {
        throw new Error('Insufficient credits');
      }
      if (!res.ok) {
        throw new Error(`Failed to start pipeline (${res.status})`);
      }

      const data = await res.json();
      const jobId = data.job_id;
      setCurrentJobId(jobId);
      loadCredits(token);
      streamJob(jobId, token);
    } catch (error: any) {
      setIsLoading(false);
      setJobState('error');
      setJobError(error.message);
      pushSystem(`Error: ${error.message}`);
    }
  };

  // EM-6: previously dead controls, now wired.
  const refreshPreview = () => setPreviewKey(k => k + 1);

  const openPreviewInTab = () => {
    if (previewUrl) window.open(previewUrl, '_blank', 'noopener');
  };

  const copyPreviewUrl = async () => {
    if (!previewUrl) return;
    const full = new URL(previewUrl, window.location.origin).href;
    try {
      await navigator.clipboard.writeText(full);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = full;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const downloadExport = async (jobId: string) => {
    if (!token) return;
    try {
      const res = await fetch(`/api/pipeline/export/${jobId}`, { headers: authHeaders(token) });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${jobId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      pushSystem(`Export error: ${err.message}`);
    }
  };

  // -------------------------------------------------------------------------
  // State 0: auth still resolving
  // -------------------------------------------------------------------------
  if (authState === 'checking') {
    return (
      <div className="h-screen flex items-center justify-center bg-dark-950">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // State: signed out — glassmorphic sign-in card
  // -------------------------------------------------------------------------
  if (authState === 'signed_out') {
    return (
      <div className="h-screen flex items-center justify-center bg-dark-950 relative overflow-hidden">
        <div className="absolute -top-32 -left-32 w-96 h-96 bg-primary-600/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
        <div className="relative w-full max-w-md p-8 rounded-2xl glass-panel glass-panel-hover shadow-2xl animate-reveal-up">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-xl bg-primary-500/10 border border-primary-500/30">
              <Zap className="w-6 h-6 text-primary-400" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-white">Emergent Workspace</h1>
              <p className="text-xs text-dark-400">Sign in to build with the agent team</p>
            </div>
          </div>
          <form onSubmit={handleSignIn} className="space-y-4">
            <input
              value={authUsername}
              onChange={(e) => setAuthUsername(e.target.value)}
              placeholder="Username"
              autoComplete="username"
              className="w-full bg-dark-800 border border-dark-700 text-white placeholder-dark-500 px-4 py-3 rounded-xl focus:outline-none focus:border-primary-500"
            />
            <input
              type="password"
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
              placeholder="Password"
              autoComplete="current-password"
              className="w-full bg-dark-800 border border-dark-700 text-white placeholder-dark-500 px-4 py-3 rounded-xl focus:outline-none focus:border-primary-500"
            />
            {authError && (
              <p className="text-sm text-red-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {authError}
              </p>
            )}
            <button
              type="submit"
              disabled={authBusy || !authUsername.trim() || !authPassword}
              className="w-full py-3 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-white font-medium transition-colors flex items-center justify-center gap-2"
            >
              {authBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogOut className="w-4 h-4 rotate-180" />}
              Sign In
            </button>
            <button
              type="button"
              onClick={handleRegister}
              disabled={authBusy || !authUsername.trim() || !authPassword}
              className="w-full py-3 bg-dark-800 hover:bg-dark-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-dark-200 font-medium transition-colors border border-dark-700"
            >
              Create account
            </button>
          </form>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // Signed in — main workspace
  // -------------------------------------------------------------------------
  return (
    <div className="h-screen flex bg-dark-950 overflow-hidden">
      {/* Left Sidebar - Agent Activity */}
      {sidebarOpen && (
        <aside className="w-80 bg-dark-900/50 backdrop-blur-md border-r border-dark-800 flex-col hidden lg:flex">
          <div className="p-4 border-b border-dark-800">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary-500" />
              Agent Activity
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {activities.length === 0 ? (
              <div className="text-center text-dark-500 py-8">
                <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p className="text-sm">Start a conversation to see agent activity</p>
              </div>
            ) : (
              activities.map((activity) => (
                <div key={activity.id} className="p-3 glass-panel glass-panel-hover rounded-xl">
                  <div className="flex items-center gap-2 mb-1">
                    <div className={`w-2 h-2 rounded-full ${
                      activity.status === 'complete' ? 'bg-green-500' :
                      activity.status === 'error' ? 'bg-red-500' :
                      'bg-primary-500 animate-pulse'
                    }`} />
                    <span className="text-xs font-medium text-white capitalize">{activity.agent}</span>
                    <span className="text-xs text-dark-500">{activity.status}</span>
                  </div>
                  <p className="text-xs text-dark-400">{activity.message}</p>
                  <p className="text-xs text-dark-500 mt-1">{mounted ? activity.timestamp.toLocaleTimeString() : ''}</p>
                </div>
              ))
            )}
          </div>
          <div className="p-4 border-t border-dark-800">
            <div className="flex items-center gap-3 p-3 glass-panel rounded-xl">
              <div className={`w-3 h-3 rounded-full ${
                currentPhase === 'complete' ? 'bg-green-500' :
                currentPhase === 'error' ? 'bg-red-500' :
                'bg-primary-500 animate-pulse'
              }`} />
              <div>
                <p className="text-xs text-dark-500">Current Phase</p>
                <p className="text-sm font-medium text-white capitalize">{currentPhase}</p>
              </div>
            </div>
          </div>
        </aside>
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat Header */}
        <header className="h-16 bg-dark-900/50 backdrop-blur-md border-b border-dark-800 flex items-center justify-between px-4 z-10">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-white">Project Workspace</h2>
            <span className="px-2 py-1 text-xs bg-primary-500/10 text-primary-400 rounded-full">v1.0.0</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-1 bg-dark-800 rounded-lg text-sm text-dark-300 font-medium mr-2 border border-dark-700">
              <Zap className="w-4 h-4 text-amber-500" />
              <span>{credits !== null ? credits : '...'} Credits</span>
            </div>
            <button
              onClick={() => setShowSettings(s => !s)}
              className={`p-2 rounded-lg transition-colors ${showSettings ? 'text-white bg-dark-800' : 'text-dark-400 hover:text-white hover:bg-dark-800'}`}
              title="Settings"
              aria-pressed={showSettings}
            >
              <Settings className="w-5 h-5" />
            </button>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 text-dark-400 hover:text-white hover:bg-dark-800 rounded-lg transition-colors"
              title="Toggle Sidebar"
              aria-pressed={sidebarOpen}
            >
              <Layers className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* EM-6: Settings panel (previously a dead button) */}
        {showSettings && (
          <div className="px-4 py-3 glass-panel rounded-b-xl mx-4 mt-2 flex items-center justify-between gap-4 z-10">
            <div className="flex items-center gap-4 text-sm text-dark-300">
              <span className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                Balance: <strong className="text-white">{credits !== null ? credits : '...'}</strong> credits
              </span>
              <span className="text-dark-500">API: /api/pipeline</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => token && loadCredits(token)}
                className="px-3 py-1.5 text-sm bg-dark-800 hover:bg-dark-700 rounded-lg text-dark-200 transition-colors border border-dark-700"
              >
                Refresh balance
              </button>
              <button
                onClick={signOut}
                className="px-3 py-1.5 text-sm bg-red-500/10 hover:bg-red-500/20 rounded-lg text-red-400 transition-colors border border-red-500/30 flex items-center gap-2"
              >
                <LogOut className="w-4 h-4" /> Sign out
              </button>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {messages.map((message) => (
            <div key={message.id} className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${
                message.role === 'user'
                  ? 'bg-primary-500'
                  : message.role === 'system'
                    ? 'bg-amber-500'
                    : 'bg-dark-800 border border-dark-700'
              }`}>
                {message.role === 'user' ? (
                  <span className="text-white text-sm font-medium">U</span>
                ) : message.role === 'system' ? (
                  <AlertCircle className="w-4 h-4 text-amber-400" />
                ) : (
                  <Terminal className="w-4 h-4 text-primary-400" />
                )}
              </div>
              <div className={`max-w-[70%] ${message.role === 'user' ? 'text-right' : ''}`}>
                <div className={`inline-block p-4 rounded-2xl ${
                  message.role === 'user'
                    ? 'bg-primary-500/20 text-white border border-primary-500/30'
                    : 'glass-panel text-white'
                }`}>
                  {message.agent && (
                    <p className="text-xs text-primary-400 mb-1 font-medium">{message.agent}</p>
                  )}
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {Boolean(message.metadata?.jobId) && (
                    <div className="mt-4 flex gap-2">
                      <button
                        onClick={() => downloadExport(String(message.metadata?.jobId))}
                        className="flex items-center gap-2 px-3 py-1.5 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm font-medium transition-colors"
                      >
                        <Download className="w-4 h-4" />
                        Download Source Code (.zip)
                      </button>
                    </div>
                  )}
                </div>
                <p className="text-xs text-dark-500 mt-1">{mounted ? message.timestamp.toLocaleTimeString() : ''}</p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-dark-800 bg-dark-900/50 backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e as unknown as React.FormEvent);
                  }
                }}
                placeholder="Type your message... (Shift+Enter for new line)"
                className="w-full bg-dark-800 border border-dark-700 text-white placeholder-dark-500 px-4 py-3 rounded-xl focus:outline-none focus:border-primary-500 resize-none min-h-[50px] max-h-[150px]"
                rows={1}
                disabled={isLoading}
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="p-3 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-white transition-colors flex items-center justify-center"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </form>
          <p className="text-xs text-dark-500 text-center mt-2">
            Press Enter to send • Shift+Enter for new line
          </p>
        </div>
      </div>

      {/* Right Panel - Live Preview with the four job states */}
      <aside className="w-96 bg-dark-900 border-l border-dark-800 flex-col hidden xl:flex">
        <div className="p-4 border-b border-dark-800 flex items-center justify-between">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <Monitor className="w-5 h-5 text-primary-500" />
            Live Preview
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={refreshPreview}
              disabled={jobState !== 'complete'}
              className="p-2 text-dark-400 hover:text-white hover:bg-dark-800 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              title="Refresh preview"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={openPreviewInTab}
              disabled={jobState !== 'complete'}
              className="p-2 text-dark-400 hover:text-white hover:bg-dark-800 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              title="Open in new tab"
            >
              <ExternalLink className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 relative">
          {/* State 1: empty — no job yet */}
          {jobState === 'empty' && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <Monitor className="w-12 h-12 text-dark-600 mb-4" />
              <p className="text-sm text-dark-400 font-medium">No build yet</p>
              <p className="text-xs text-dark-500 mt-1">Describe your app in the chat and the live preview will appear here.</p>
            </div>
          )}

          {/* State 2: loading — pipeline running */}
          {jobState === 'loading' && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <Loader2 className="w-10 h-10 animate-spin text-primary-500 mb-4" />
              <p className="text-sm text-white font-medium capitalize">{currentPhase}...</p>
              <p className="text-xs text-dark-500 mt-1">The agent team is building your app. This usually takes a minute or two.</p>
            </div>
          )}

          {/* State 3: error — pipeline failed */}
          {jobState === 'error' && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <AlertCircle className="w-10 h-10 text-red-500 mb-4" />
              <p className="text-sm text-white font-medium">Build failed</p>
              <p className="text-xs text-red-400/80 mt-2 max-w-xs break-words">{jobError || 'The pipeline stopped with an error.'}</p>
              <p className="text-xs text-dark-500 mt-2">Send another message to retry.</p>
            </div>
          )}

          {/* State 4: complete — live iframe */}
          {jobState === 'complete' && previewUrl && (
            <iframe
              key={previewKey}
              src={previewUrl}
              className="w-full h-full border-0"
              title="Live Preview"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
            />
          )}

          {jobState === 'complete' && (
            <div className="absolute bottom-4 right-4 flex gap-2">
              <button
                onClick={copyPreviewUrl}
                className="p-2 glass-panel glass-panel-hover rounded-lg text-dark-300 hover:text-white transition-colors"
                title="Copy preview URL"
              >
                {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
              </button>
              <button
                onClick={() => currentJobId && downloadExport(currentJobId)}
                className="p-2 bg-primary-600 hover:bg-primary-500 rounded-lg text-white shadow-glow-primary transition-all hover:scale-105"
                title="Download code (.zip)"
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-dark-800 bg-dark-950/50">
          <div className="flex items-center gap-2 text-xs text-dark-400">
            <span className={`w-2 h-2 rounded-full ${
              jobState === 'complete' ? 'bg-green-500' :
              jobState === 'loading' ? 'bg-amber-500 animate-pulse' :
              jobState === 'error' ? 'bg-red-500' : 'bg-dark-600'
            }`} />
            <span>
              {jobState === 'complete' ? `Preview live at ${previewUrl}` :
               jobState === 'loading' ? 'Build in progress...' :
               jobState === 'error' ? 'Build failed' :
               'Waiting for first build'}
            </span>
          </div>
        </div>
      </aside>
    </div>
  );
}
