import { useState, type FormEvent } from "react";
import { BarChart3, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getStats, StatsResponse } from "@/lib/api";
import { toast } from "@/hooks/use-toast";

const StatsCard = () => {
  const [code, setCode] = useState("");
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLookup = async (e: FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;

    setLoading(true);
    setStats(null);
    try {
      const data = await getStats(code.trim());
      setStats(data);
    } catch (err: any) {
      const message = err.response?.data?.error || err.response?.data?.message || "Short code not found.";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <BarChart3 className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Link Analytics</h2>
      </div>

      <form onSubmit={handleLookup} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Enter short code..."
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button type="submit" variant="secondary" disabled={loading || !code.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Lookup"}
        </Button>
      </form>

      {stats && (
        <div className="rounded-xl border bg-card p-4 space-y-3 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">Original URL</p>
            <a
              href={stats.original_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline break-all"
            >
              {stats.original_url}
            </a>
          </div>
          <div className="flex gap-6">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Clicks</p>
              <p className="text-2xl font-bold">{stats.clicks}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Expiry</p>
              <p className="text-sm font-medium">
                {stats.expiry ? new Date(stats.expiry).toLocaleString() : "Never"}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StatsCard;
