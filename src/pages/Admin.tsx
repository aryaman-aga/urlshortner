import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity, Cpu, Database, Globe, HardDrive, LogOut,
  RefreshCw, Server, Users, Zap, BarChart3, ExternalLink,
  Clock, Hash, MousePointerClick, Timer,
} from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";
import { getAdminStats, type AdminStats } from "@/lib/api";
import { clearAuth, getAuthUsername } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const StatCard = ({
  icon: Icon,
  label,
  value,
  sub,
  accent = "from-primary to-primary/70",
}: {
  icon: any;
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) => (
  <div className="relative group rounded-xl border border-border/40 bg-card/60 backdrop-blur-sm p-5 shadow-sm hover:border-border/80 hover:bg-card/80 transition-all">
    <div className={`absolute inset-0 rounded-xl bg-gradient-to-br ${accent} opacity-[0.03] group-hover:opacity-[0.06] transition-opacity pointer-events-none`} />
    <div className="flex items-start justify-between">
      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground tracking-wider uppercase">{label}</p>
        <p className="text-2xl font-bold tabular-nums tracking-tight">{value}</p>
        {sub && <p className="text-xs text-muted-foreground/70">{sub}</p>}
      </div>
      <div className={`h-9 w-9 rounded-lg bg-gradient-to-br ${accent} flex items-center justify-center shadow-sm`}>
        <Icon className="h-4 w-4 text-primary-foreground" />
      </div>
    </div>
  </div>
);

const ProgressBar = ({ value, max, label }: { value: number; max: number; label: string }) => (
  <div className="space-y-1">
    <div className="flex justify-between text-xs text-muted-foreground">
      <span>{label}</span>
      <span className="tabular-nums">{max ? ((value / max) * 100).toFixed(1) : 0}%</span>
    </div>
    <div className="h-1.5 rounded-full bg-muted/50 overflow-hidden">
      <div
        className="h-full rounded-full bg-gradient-to-r from-primary/60 to-primary transition-all duration-500"
        style={{ width: `${max ? Math.min((value / max) * 100, 100) : 0}%` }}
      />
    </div>
  </div>
);

const Admin = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getAdminStats();
      setStats(data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        clearAuth();
        navigate("/login", { replace: true });
        return;
      }
      setError(err.response?.data?.error || "Failed to load stats");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleLogout = () => {
    clearAuth();
    navigate("/login", { replace: true });
  };

  const handleBack = () => navigate("/");

  const username = getAuthUsername();

  const fmtBytes = (b: number) => {
    if (b < 1024) return `${b} B`;
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / (1024 * 1024)).toFixed(1)} MB`;
  };

  const fmtTime = (s: number) => {
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${d}d ${h}h ${m}m ${sec}s`;
  };

  return (
    <div className="h-screen bg-background flex flex-col overflow-hidden">
      <header className="border-b border-border/40 bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center justify-between px-4 lg:px-8 h-14">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-sm">
              <Server className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold tracking-tight">Admin</span>
            <span className="hidden sm:inline text-xs text-muted-foreground border-l border-border/40 pl-3 ml-1">
              System Overview
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={handleBack} className="text-muted-foreground hover:text-foreground">
              <BarChart3 className="h-4 w-4 mr-1.5" />
              <span className="hidden sm:inline">Dashboard</span>
            </Button>
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={handleLogout} className="text-muted-foreground hover:text-foreground">
              <LogOut className="h-4 w-4 mr-1.5" />
              <span className="hidden sm:inline">Logout</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-auto p-4 lg:p-6">
        {error && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Cpu className="h-12 w-12 text-destructive/50 mb-4" />
            <p className="text-lg font-semibold text-destructive">Error</p>
            <p className="text-sm text-muted-foreground mt-1 mb-4">{error}</p>
            <Button onClick={fetchStats} variant="outline">
              <RefreshCw className="h-4 w-4 mr-1.5" />
              Retry
            </Button>
          </div>
        )}

        {loading && !stats && !error && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-28 rounded-xl" />
              ))}
            </div>
            <Skeleton className="h-64 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
          </div>
        )}

        {stats && (
          <div className="space-y-6 animate-in fade-in duration-500">
            {/* Hero */}
            <div className="relative rounded-xl border border-border/40 bg-card/60 backdrop-blur-sm p-6 overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent pointer-events-none" />
              <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
                    <Activity className="h-5 w-5 text-primary" />
                    System Health
                  </h1>
                  <p className="text-sm text-muted-foreground mt-1">
                    All metrics are live — refreshed on every request.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/50 px-3 py-1.5 rounded-full">
                    <Timer className="h-3 w-3" />
                    {stats.system.uptime_human}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/50 px-3 py-1.5 rounded-full">
                    <Hash className="h-3 w-3" />
                    {stats.system.requests_served.toLocaleString()} req
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchStats} disabled={loading}>
                    <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
                    {loading ? "Loading" : "Refresh"}
                  </Button>
                </div>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard icon={Globe} label="Total URLs" value={stats.urls.total.toLocaleString()} sub={`${stats.urls.expired.toLocaleString()} expired`} />
              <StatCard icon={MousePointerClick} label="Total Clicks" value={stats.urls.total_clicks.toLocaleString()} sub="across all links" accent="from-amber-500 to-amber-600" />
              <StatCard icon={Users} label="Users" value={stats.users.total.toLocaleString()} sub="registered accounts" accent="from-emerald-500 to-emerald-600" />
              <StatCard icon={BarChart3} label="Avg Object Size" value={fmtBytes(stats.database.avg_object_size_bytes)} sub="per document" accent="from-violet-500 to-violet-600" />
              <StatCard icon={Database} label="Database Size" value={`${stats.database.size_mb.toFixed(1)} MB`} sub={`${stats.database.objects.toLocaleString()} objects`} />
              <StatCard icon={HardDrive} label="Index Size" value={`${stats.database.index_size_mb.toFixed(1)} MB`} sub={`${stats.database.collections} collections`} accent="from-cyan-500 to-cyan-600" />
              <StatCard icon={Server} label="Redis Keys" value={stats.redis.keys?.toLocaleString() ?? "N/A"} sub={stats.redis.connected ? "connected" : "disconnected"} accent={stats.redis.connected ? "from-rose-500 to-rose-600" : "from-muted-foreground to-muted"} />
              <StatCard icon={Cpu} label="Redis Hit Rate" value={stats.redis.hit_rate != null ? `${(stats.redis.hit_rate * 100).toFixed(1)}%` : "N/A"} sub={`${(stats.redis.hits ?? 0).toLocaleString()} hits / ${(stats.redis.misses ?? 0).toLocaleString()} misses`} accent="from-orange-500 to-orange-600" />
            </div>

            {/* Redis & System Detail */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="rounded-xl border border-border/40 bg-card/60 backdrop-blur-sm p-5 shadow-sm">
                <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase flex items-center gap-2 mb-4">
                  <Cpu className="h-4 w-4 text-primary" />
                  Redis Cache
                </h2>
                {stats.redis.connected ? (
                  <div className="space-y-3">
                    <ProgressBar value={stats.redis.hits ?? 0} max={(stats.redis.hits ?? 0) + (stats.redis.misses ?? 1)} label="Cache Hit Rate" />
                    <div className="grid grid-cols-2 gap-3 pt-2">
                      <div className="rounded-lg bg-muted/30 p-3">
                        <p className="text-xs text-muted-foreground">Memory Used</p>
                        <p className="text-lg font-bold tabular-nums">{fmtBytes(stats.redis.used_memory_bytes ?? 0)}</p>
                      </div>
                      <div className="rounded-lg bg-muted/30 p-3">
                        <p className="text-xs text-muted-foreground">Cached Keys</p>
                        <p className="text-lg font-bold tabular-nums">{stats.redis.keys?.toLocaleString() ?? 0}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 text-sm text-muted-foreground">
                    <div className="h-2 w-2 rounded-full bg-destructive" />
                    Redis is {stats.redis.configured === false ? "not configured" : "disconnected"}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-border/40 bg-card/60 backdrop-blur-sm p-5 shadow-sm">
                <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase flex items-center gap-2 mb-4">
                  <Activity className="h-4 w-4 text-primary" />
                  System
                </h2>
                <div className="space-y-3">
                  <div className="flex justify-between items-center py-1.5 border-b border-border/20">
                    <span className="text-sm text-muted-foreground">Uptime</span>
                    <span className="text-sm font-mono tabular-nums">{fmtTime(stats.system.uptime_seconds)}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 border-b border-border/20">
                    <span className="text-sm text-muted-foreground">Requests Served</span>
                    <span className="text-sm font-mono tabular-nums">{stats.system.requests_served.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 border-b border-border/20">
                    <span className="text-sm text-muted-foreground">Started At</span>
                    <span className="text-sm font-mono tabular-nums">{new Date(stats.system.started_at).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 border-b border-border/20">
                    <span className="text-sm text-muted-foreground">Authenticated</span>
                    <span className="text-sm font-mono tabular-nums text-emerald-400">{username ?? "unknown"}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5">
                    <span className="text-sm text-muted-foreground">Database</span>
                    <span className="text-sm font-mono tabular-nums">{stats.database.objects.toLocaleString()} docs in {stats.database.collections} collections</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Top URLs Table */}
            <div className="rounded-xl border border-border/40 bg-card/60 backdrop-blur-sm shadow-sm">
              <div className="flex items-center gap-2 p-5 pb-3">
                <Zap className="h-5 w-5 text-primary" />
                <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">Top URLs by clicks</h2>
              </div>
              {stats.top_urls.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <BarChart3 className="h-8 w-8 mb-2 opacity-30" />
                  <p className="text-sm">No URLs yet</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/20 text-xs text-muted-foreground uppercase tracking-wider">
                        <th className="text-left px-5 py-3 font-medium">#</th>
                        <th className="text-left px-5 py-3 font-medium">Short Code</th>
                        <th className="text-left px-5 py-3 font-medium">Original URL</th>
                        <th className="text-right px-5 py-3 font-medium">Clicks</th>
                        <th className="text-right px-5 py-3 font-medium hidden sm:table-cell">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.top_urls.map((u, i) => (
                        <tr key={u.short_code} className="border-b border-border/10 hover:bg-accent/20 transition-colors">
                          <td className="px-5 py-3 text-muted-foreground tabular-nums">{i + 1}</td>
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-1.5">
                              <ExternalLink className="h-3 w-3 text-primary" />
                              <span className="font-mono font-semibold text-primary">{u.short_code}</span>
                            </div>
                          </td>
                          <td className="px-5 py-3 max-w-[300px] truncate text-muted-foreground" title={u.original_url}>
                            {u.original_url}
                          </td>
                          <td className="px-5 py-3 text-right font-mono tabular-nums font-semibold">{u.clicks.toLocaleString()}</td>
                          <td className="px-5 py-3 text-right text-muted-foreground hidden sm:table-cell tabular-nums">
                            {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default Admin;