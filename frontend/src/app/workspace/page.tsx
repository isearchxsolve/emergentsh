'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Loader2, Copy, Download, Terminal, Layers, Zap, AlertCircle, MessageSquare, Monitor, Settings, LogOut, RefreshCw, ExternalLink, Check, Laptop, Tablet, Smartphone, Maximize2, X } from 'lucide-react';

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
type PreviewDevice = 'desktop' | 'tablet' | 'mobile';

const TOKEN_KEY = 'emergent_token';

function readableApiError(payload: unknown, fallback: string): string {
  const detail = (payload as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(item => {
      if (typeof item === 'string') return item;
      if (item && typeof item === 'object' && 'msg' in item) return String((item as { msg: unknown }).msg);
      return '';
    }).filter(Boolean);
    if (messages.length) return messages.join(' · ');
  }
  return fallback;
}

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
  const [previewDevice, setPreviewDevice] = useState<PreviewDevice>('desktop');
  const [previewExpanded, setPreviewExpanded] = useState(false);
  const [outputTarget, setOutputTarget] = useState('web');

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
        throw new Error(readableApiError(detail, `Sign-in failed (${res.status})`));
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
        throw new Error(readableApiError(detail, `Registration failed (${res.status})`));
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
      let sawTerminalEvent = false;
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
          if (payload.event === 'pipeline_complete' || payload.event === 'pipeline_error') {
            sawTerminalEvent = true;
          }
          handleStreamEvent(payload, jobId);
        }
      }
      // A proxy, reload, or browser stream boundary can close after the
      // server persisted the terminal status but before the final SSE frame
      // reaches React. Reuse the existing bounded status reconciliation path
      // instead of leaving the workspace indefinitely in "building".
      if (!sawTerminalEvent) {
        throw new Error('Progress stream closed before a terminal event');
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
        setOutputTarget(status.target || 'web');
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
        setOutputTarget(payload.data?.target || 'web');
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
      setOutputTarget(data.target || 'web');
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

  const previewWidth: Record<PreviewDevice, string> = {
    desktop: '100%',
    tablet: '768px',
    mobile: '390px',
  };

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
      <div className="workspace-aurora h-screen flex items-center justify-center">
        <div className="grid h-16 w-16 place-items-center rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.05] shadow-[0_0_40px_rgba(34,211,238,.12)] backdrop-blur-2xl">
          <Loader2 className="w-7 h-7 animate-spin text-cyan-300" />
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // State: signed out — glassmorphic sign-in card
  // -------------------------------------------------------------------------
  if (authState === 'signed_out') {
    return (
      <div className="workspace-aurora h-screen flex items-center justify-center relative overflow-hidden px-5">
        <div className="absolute inset-0 bg-grid-fade opacity-40" />
        <div className="absolute -top-32 -left-32 w-[30rem] h-[30rem] bg-cyan-400/10 rounded-full blur-[110px]" />
        <div className="absolute -bottom-32 -right-32 w-[34rem] h-[34rem] bg-violet-600/15 rounded-full blur-[120px]" />
        <div className="relative w-full max-w-md p-8 rounded-[1.8rem] border border-white/[0.09] bg-[#0a0c14]/70 shadow-[0_40px_100px_rgba(0,0,0,.45)] backdrop-blur-2xl animate-reveal-up">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-cyan-300 to-violet-500 shadow-[0_0_26px_rgba(34,211,238,.2)]">
              <Zap className="w-5 h-5 text-slate-950 fill-current" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-[-.03em] text-white">Emergent<span className="text-cyan-300">SH</span> Studio</h1>
              <p className="text-xs text-slate-500">Your multi-agent software team</p>
            </div>
          </div>
          <form onSubmit={handleSignIn} className="space-y-4">
            <input
              value={authUsername}
              onChange={(e) => setAuthUsername(e.target.value)}
              placeholder="Username"
              autoComplete="username"
              className="w-full bg-white/[0.035] border border-white/[0.08] text-white placeholder-slate-600 px-4 py-3.5 rounded-xl focus:outline-none focus:border-cyan-300/40 focus:bg-cyan-300/[0.025] transition"
            />
            <input
              type="password"
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
              placeholder="Password"
              autoComplete="current-password"
              className="w-full bg-white/[0.035] border border-white/[0.08] text-white placeholder-slate-600 px-4 py-3.5 rounded-xl focus:outline-none focus:border-cyan-300/40 focus:bg-cyan-300/[0.025] transition"
            />
            {authError && (
              <p className="text-sm text-red-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {authError}
              </p>
            )}
            <button
              type="submit"
              disabled={authBusy || !authUsername.trim() || !authPassword}
              className="w-full py-3.5 bg-gradient-to-r from-cyan-300 to-blue-400 hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-slate-950 font-semibold transition flex items-center justify-center gap-2 shadow-[0_0_26px_rgba(34,211,238,.16)]"
            >
              {authBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogOut className="w-4 h-4 rotate-180" />}
              Sign In
            </button>
            <button
              type="button"
              onClick={handleRegister}
              disabled={authBusy || !authUsername.trim() || !authPassword}
              className="w-full py-3.5 bg-white/[0.035] hover:bg-white/[0.065] disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-slate-300 font-medium transition border border-white/[0.08]"
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
    <div className="workspace-aurora h-screen flex overflow-hidden text-slate-100">
      {/* Left Sidebar - Agent Activity */}
      {sidebarOpen && (
        <aside className="w-[18.5rem] m-3 mr-0 rounded-[1.4rem] border border-white/[0.07] bg-[#090b12]/65 shadow-2xl shadow-black/20 backdrop-blur-2xl flex-col hidden lg:flex overflow-hidden">
          <div className="p-5 border-b border-white/[0.06]">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[.22em] text-cyan-300/70">Execution graph</p>
            <h3 className="font-semibold tracking-[-.02em] text-white flex items-center gap-2">
              <Zap className="w-4 h-4 text-cyan-300 fill-current" />
              Agent flow
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
            {activities.length === 0 ? (
              <div className="text-center text-slate-600 py-12 px-5">
                <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-2xl border border-violet-300/10 bg-violet-300/[0.04]"><MessageSquare className="w-5 h-5 text-violet-300/70" /></div>
                <p className="text-sm text-slate-400">Your agent team is ready</p>
                <p className="mt-2 text-xs leading-5">Describe a product to watch each specialist come online.</p>
              </div>
            ) : (
              activities.map((activity) => (
                <div key={activity.id} className="relative p-3.5 rounded-xl border border-white/[0.07] bg-white/[0.025] transition hover:bg-white/[0.045]">
                  <div className="flex items-center gap-2 mb-1">
                    <div className={`w-2 h-2 rounded-full ${
                      activity.status === 'complete' ? 'bg-green-500' :
                      activity.status === 'error' ? 'bg-red-500' :
                      'bg-cyan-300 animate-pulse shadow-[0_0_12px_rgba(34,211,238,.7)]'
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
          <div className="p-4 border-t border-white/[0.06]">
            <div className="flex items-center gap-3 p-3.5 rounded-xl border border-white/[0.07] bg-gradient-to-r from-white/[0.04] to-transparent">
              <div className={`w-3 h-3 rounded-full ${
                currentPhase === 'complete' ? 'bg-green-500' :
                currentPhase === 'error' ? 'bg-red-500' :
                'bg-cyan-300 animate-pulse shadow-[0_0_12px_rgba(34,211,238,.7)]'
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
      <div className="flex-1 flex flex-col min-w-0 m-3 gap-3">
        {/* Chat Header */}
        <header className="h-16 rounded-[1.25rem] border border-white/[0.07] bg-[#090b12]/65 shadow-xl shadow-black/10 backdrop-blur-2xl flex items-center justify-between px-5 z-10">
          <div className="flex items-center gap-3">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-cyan-300 to-violet-500 text-slate-950 shadow-[0_0_20px_rgba(34,211,238,.16)]"><Zap className="h-4 w-4 fill-current" /></span>
            <div><h2 className="font-semibold tracking-[-.025em] text-white">Project Studio</h2><p className="text-[10px] text-slate-600">EmergentSH · live workspace</p></div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-300/[0.06] rounded-xl text-xs text-amber-100/80 font-medium mr-1 border border-amber-300/10">
              <Zap className="w-3.5 h-3.5 text-amber-300 fill-current" />
              <span>{credits !== null ? credits : '...'} Credits</span>
            </div>
            <button
              onClick={() => setShowSettings(s => !s)}
              className={`p-2 rounded-xl border transition ${showSettings ? 'text-white bg-white/[0.08] border-white/10' : 'text-slate-500 border-transparent hover:text-white hover:bg-white/[0.05]'}`}
              title="Settings"
              aria-pressed={showSettings}
            >
              <Settings className="w-5 h-5" />
            </button>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 text-slate-500 hover:text-white hover:bg-white/[0.05] rounded-xl transition"
              title="Toggle Sidebar"
              aria-pressed={sidebarOpen}
            >
              <Layers className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* EM-6: Settings panel (previously a dead button) */}
        {showSettings && (
          <div className="px-4 py-3 border border-white/[0.07] bg-[#0b0e17]/85 rounded-2xl flex items-center justify-between gap-4 z-10 backdrop-blur-2xl">
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
        <div className="flex-1 overflow-y-auto rounded-[1.4rem] border border-white/[0.055] bg-[#070910]/50 p-5 space-y-6 shadow-inner shadow-black/20 backdrop-blur-xl">
          {messages.map((message) => (
            <div key={message.id} className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
                message.role === 'user'
                  ? 'bg-gradient-to-br from-cyan-300 to-blue-500 text-slate-950 shadow-[0_0_20px_rgba(34,211,238,.16)]'
                  : message.role === 'system'
                    ? 'bg-amber-300/10 border border-amber-300/20'
                    : 'bg-violet-300/10 border border-violet-300/15'
              }`}>
                {message.role === 'user' ? (
                  <span className="text-slate-950 text-sm font-bold">U</span>
                ) : message.role === 'system' ? (
                  <AlertCircle className="w-4 h-4 text-amber-400" />
                ) : (
                  <Terminal className="w-4 h-4 text-violet-200" />
                )}
              </div>
              <div className={`max-w-[76%] ${message.role === 'user' ? 'text-right' : ''}`}>
                <div className={`inline-block p-4 rounded-2xl ${
                  message.role === 'user'
                    ? 'bg-gradient-to-br from-cyan-300/15 to-blue-500/10 text-white border border-cyan-300/15 shadow-[0_16px_40px_rgba(0,0,0,.12)]'
                    : 'bg-white/[0.035] border border-white/[0.07] text-slate-200 shadow-[0_16px_40px_rgba(0,0,0,.12)] backdrop-blur-xl'
                }`}>
                  {message.agent && (
                    <p className="text-[10px] uppercase tracking-[.18em] text-violet-200/70 mb-2 font-semibold">{message.agent}</p>
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
        <div className="rounded-[1.25rem] border border-white/[0.07] bg-[#090b12]/75 p-3 backdrop-blur-2xl">
          <form onSubmit={handleSubmit} className="flex gap-2">
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
                className="w-full bg-transparent border-0 text-white placeholder-slate-600 px-3 py-3 rounded-xl focus:outline-none resize-none min-h-[50px] max-h-[150px]"
                rows={1}
                disabled={isLoading}
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="p-3.5 bg-gradient-to-br from-cyan-300 to-blue-400 hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-slate-950 transition flex items-center justify-center shadow-[0_0_24px_rgba(34,211,238,.16)]"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </form>
          <p className="text-[10px] text-slate-700 text-center mt-1">
            Enter to build · Shift + Enter for a new line
          </p>
        </div>
      </div>

      {/* Right Panel - Live Preview with the four job states */}
      <aside className="w-[27rem] m-3 ml-0 rounded-[1.4rem] border border-white/[0.07] bg-[#090b12]/65 shadow-2xl shadow-black/20 backdrop-blur-2xl flex-col hidden xl:flex overflow-hidden">
        <div className="p-4 border-b border-white/[0.06] space-y-3">
          <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <Monitor className="w-4 h-4 text-cyan-300" />
            Preview studio
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
              onClick={() => setPreviewExpanded(true)}
              disabled={jobState !== 'complete'}
              className="p-2 text-dark-400 hover:text-white hover:bg-dark-800 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              title="Expand preview"
            >
              <Maximize2 className="w-4 h-4" />
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
          <div className="flex rounded-xl border border-white/[0.06] bg-black/25 p-1" aria-label="Preview device">
            {([
              ['desktop', Laptop, 'Desktop'],
              ['tablet', Tablet, 'Tablet'],
              ['mobile', Smartphone, 'Mobile'],
            ] as const).map(([device, Icon, label]) => (
              <button key={device} type="button" onClick={() => setPreviewDevice(device)}
                aria-pressed={previewDevice === device} title={`${label} preview`}
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] transition ${previewDevice === device ? 'bg-white/[0.09] text-cyan-200 shadow-inner' : 'text-slate-600 hover:text-slate-300'}`}>
                <Icon className="h-3.5 w-3.5" /> {label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 relative bg-[#05070c]">
          {/* State 1: empty — no job yet */}
          {jobState === 'empty' && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 bg-grid-fade">
              <div className="mb-5 grid h-16 w-16 place-items-center rounded-2xl border border-cyan-300/10 bg-cyan-300/[0.035] shadow-[0_0_50px_rgba(34,211,238,.08)]"><Monitor className="w-6 h-6 text-cyan-200/70" /></div>
              <p className="text-sm text-slate-300 font-medium">Your canvas is ready</p>
              <p className="text-xs text-slate-600 mt-2 max-w-[15rem] leading-5">Describe the product. The live interface will materialize here as agents build.</p>
            </div>
          )}

          {/* State 2: loading — pipeline running */}
          {jobState === 'loading' && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <div className="relative mb-5"><div className="absolute inset-0 rounded-full bg-cyan-300/20 blur-xl animate-pulse"/><Loader2 className="relative w-10 h-10 animate-spin text-cyan-300" /></div>
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
            <div className="h-full overflow-auto bg-[radial-gradient(circle_at_50%_0%,rgba(16,185,129,.12),transparent_40%),#030509] p-3">
              <div className="mx-auto h-full min-h-[32rem] overflow-hidden rounded-xl border border-emerald-300/10 bg-white shadow-[0_24px_80px_rgba(0,0,0,.55),0_0_40px_rgba(16,185,129,.08)] transition-[width] duration-300" style={{ width: previewWidth[previewDevice], maxWidth: '100%' }}>
                <iframe key={previewKey} src={previewUrl} className="w-full h-full border-0" title={`${previewDevice} app preview`} sandbox="allow-scripts allow-forms allow-popups allow-modals" />
              </div>
            </div>
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

        <div className="p-4 border-t border-white/[0.06] bg-black/20">
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

      {previewExpanded && previewUrl && (
        <div className="fixed inset-0 z-50 flex flex-col bg-[#030509]/95 backdrop-blur-2xl" role="dialog" aria-modal="true" aria-label="Expanded app preview">
          <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-3">
            <div><p className="text-sm font-semibold text-white">Live app preview</p><p className="text-[11px] text-emerald-300/60">{outputTarget === 'web' || outputTarget === 'pwa' ? 'Interactive runtime' : `${outputTarget} interactive simulation`} · {previewDevice} viewport</p></div>
            <div className="flex items-center gap-2">
              {([['desktop', Laptop], ['tablet', Tablet], ['mobile', Smartphone]] as const).map(([device, Icon]) => (
                <button key={device} onClick={() => setPreviewDevice(device)} aria-pressed={previewDevice === device} title={`${device} preview`} className={`rounded-lg p-2 transition ${previewDevice === device ? 'bg-emerald-300/15 text-emerald-200' : 'text-slate-500 hover:bg-white/[0.06] hover:text-white'}`}><Icon className="h-4 w-4" /></button>
              ))}
              <button onClick={refreshPreview} title="Refresh preview" className="rounded-lg p-2 text-slate-500 hover:bg-white/[0.06] hover:text-white"><RefreshCw className="h-4 w-4" /></button>
              <button onClick={() => setPreviewExpanded(false)} title="Close preview" className="ml-2 rounded-lg border border-white/[0.08] p-2 text-slate-400 hover:bg-white/[0.07] hover:text-white"><X className="h-4 w-4" /></button>
            </div>
          </div>
          <div className="flex-1 overflow-auto bg-[radial-gradient(circle_at_50%_0%,rgba(16,185,129,.14),transparent_38%),radial-gradient(circle_at_95%_95%,rgba(217,70,239,.1),transparent_32%)] p-5">
            <div className="mx-auto h-full min-h-[38rem] overflow-hidden rounded-2xl border border-emerald-200/10 bg-white shadow-[0_30px_120px_rgba(0,0,0,.7),0_0_70px_rgba(16,185,129,.1)] transition-[width] duration-300" style={{ width: previewWidth[previewDevice], maxWidth: '100%' }}>
              <iframe key={`expanded-${previewKey}`} src={previewUrl} className="h-full w-full border-0" title={`Expanded ${previewDevice} app preview`} sandbox="allow-scripts allow-forms allow-popups allow-modals" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
