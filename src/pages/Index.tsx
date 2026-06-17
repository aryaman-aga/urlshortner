import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Scissors, LogOut, RefreshCw, BarChart3, ExternalLink, Zap,
  Pencil, Trash2, Loader2, Server,
} from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";
import ShortenForm from "@/components/ShortenForm";
import ResultCard from "@/components/ResultCard";
import StatsCard from "@/components/StatsCard";
import { listUrls, updateUrl, deleteUrl, ShortenResponse, type UrlItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { clearAuth } from "@/lib/auth";
import { toast } from "@/hooks/use-toast";

const Index = () => {
  const navigate = useNavigate();
  const [result, setResult] = useState<ShortenResponse | null>(null);
  const [urls, setUrls] = useState<UrlItem[]>([]);
  const [urlsLoading, setUrlsLoading] = useState(false);

  const [editingItem, setEditingItem] = useState<UrlItem | null>(null);
  const [editUrl, setEditUrl] = useState("");
  const [editAlias, setEditAlias] = useState("");
  const [editExpiry, setEditExpiry] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  const [deletingCode, setDeletingCode] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  const handleLogout = () => {
    clearAuth();
    navigate("/login", { replace: true });
  };

  const loadUrls = async () => {
    setUrlsLoading(true);
    try {
      const data = await listUrls({ limit: 100, skip: 0 });
      setUrls(data.items);
    } catch {
      toast({ title: "Error", description: "Failed to load links", variant: "destructive" });
    } finally {
      setUrlsLoading(false);
    }
  };

  useEffect(() => {
    loadUrls();
  }, []);

  const openEdit = (item: UrlItem) => {
    setEditingItem(item);
    setEditUrl(item.original_url);
    setEditAlias(item.short_code);
    setEditExpiry(item.expiry ?? "");
    setEditOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingItem) return;
    if (!editUrl.trim()) return;

    setEditSaving(true);
    try {
      await updateUrl(editingItem.short_code, {
        url: editUrl.trim(),
        custom_alias: editAlias.trim() || undefined,
        expiry: editExpiry || null,
      });
      toast({ title: "Updated", description: "Link updated successfully." });
      setEditingItem(null);
      setEditOpen(false);
      loadUrls();
    } catch (err: any) {
      const message = err.response?.data?.error || "Failed to update link";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setEditSaving(false);
    }
  };

  const handleDelete = async (shortCode: string) => {
    setDeletingCode(shortCode);
    try {
      await deleteUrl(shortCode);
      toast({ title: "Deleted", description: "Link removed." });
      setUrls((prev) => prev.filter((u) => u.short_code !== shortCode));
    } catch (err: any) {
      const message = err.response?.data?.error || "Failed to delete link";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setDeletingCode(null);
    }
  };

  return (
    <div className="h-screen bg-background flex flex-col overflow-hidden">
      <header className="border-b border-border/40 bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center justify-between px-4 lg:px-8 h-14">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-sm">
              <Scissors className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold tracking-tight">Sniplink</span>
            <span className="hidden sm:inline text-xs text-muted-foreground border-l border-border/40 pl-3 ml-1">
              URL Shortener
            </span>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={() => navigate("/aa/admin")} className="text-muted-foreground hover:text-foreground">
              <Server className="h-4 w-4 mr-1.5" />
              <span className="hidden sm:inline">Admin</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={handleLogout} className="text-muted-foreground hover:text-foreground">
              <LogOut className="h-4 w-4 mr-1.5" />
              <span className="hidden sm:inline">Logout</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 lg:p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
          <div className="h-full space-y-5 overflow-y-auto scrollbar-hide">
            <div>
              <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                <Zap className="h-5 w-5 text-primary" />
                Shorten a link
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                Paste a URL, optionally set an alias and expiry.
              </p>
            </div>

            <div className="rounded-xl border border-border/50 bg-card p-5 shadow-sm">
              <ShortenForm onResult={setResult} />
              {result && (
                <div className="mt-5 pt-5 border-t border-border/40">
                  <ResultCard result={result} />
                </div>
              )}
            </div>

            <div className="rounded-xl border border-border/50 bg-card p-5 shadow-sm">
              <StatsCard />
            </div>
          </div>

          <div className="h-full rounded-xl border border-border/50 bg-card shadow-sm flex flex-col">
            <div className="flex items-center justify-between p-5 pb-0">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">My Links</h2>
                <span className="text-xs text-muted-foreground bg-muted/50 px-2 py-0.5 rounded-full">
                  {urls.length}
                </span>
              </div>
              <Button variant="outline" size="sm" onClick={loadUrls} disabled={urlsLoading}>
                <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${urlsLoading ? "animate-spin" : ""}`} />
                {urlsLoading ? "Loading" : "Refresh"}
              </Button>
            </div>

            <div className="flex-1 overflow-auto p-5 scrollbar-hide">
              {urls.length === 0 && !urlsLoading ? (
                <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground py-16">
                  <BarChart3 className="h-10 w-10 mb-3 opacity-30" />
                  <p className="text-sm font-medium">No links yet</p>
                  <p className="text-xs mt-1">Shorten your first URL and it'll show up here.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {urls.map((item) => (
                    <div
                      key={item.short_code}
                      className="group flex items-center gap-3 rounded-lg border border-border/40 bg-background/50 px-4 py-3 hover:border-border hover:bg-accent/30 transition-all"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <a
                            href={item.short_url ?? `/${item.short_code}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-semibold text-primary hover:underline truncate"
                          >
                            <ExternalLink className="h-3 w-3 inline mr-1 -mt-0.5" />
                            {item.short_code}
                          </a>
                          <span className="text-xs tabular-nums font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
                            {item.clicks} click{item.clicks !== 1 ? "s" : ""}
                          </span>
                          {item.expiry && (
                            <span className="text-xs text-muted-foreground">
                              expires {new Date(item.expiry).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                        <a
                          href={item.original_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-muted-foreground hover:text-foreground truncate block mt-0.5 transition-colors"
                          title={item.original_url}
                        >
                          {item.original_url}
                        </a>
                      </div>

                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Dialog open={editOpen} onOpenChange={(open) => { setEditOpen(open); if (!open) setEditingItem(null); }}>
                          <DialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(item)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="sm:max-w-md">
                            <DialogHeader>
                              <DialogTitle>Edit Link</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 pt-2">
                              <div className="space-y-2">
                                <Label htmlFor="edit-url">URL</Label>
                                <Input id="edit-url" value={editUrl} onChange={(e) => setEditUrl(e.target.value)} placeholder="https://example.com" />
                              </div>
                              <div className="space-y-2">
                                <Label htmlFor="edit-alias">Short link</Label>
                                <Input id="edit-alias" value={editAlias} onChange={(e) => setEditAlias(e.target.value)} placeholder="my-link" />
                              </div>
                              <div className="space-y-2">
                                <Label htmlFor="edit-expiry">Expiry (optional)</Label>
                                <Input id="edit-expiry" type="datetime-local" value={editExpiry} onChange={(e) => setEditExpiry(e.target.value)} />
                              </div>
                              <div className="flex justify-end gap-2 pt-2">
                                <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
                                <Button onClick={handleSaveEdit} disabled={editSaving || !editUrl.trim()}>
                                  {editSaving ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : null}
                                  Save
                                </Button>
                              </div>
                            </div>
                          </DialogContent>
                        </Dialog>

                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive">
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete this link?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This will permanently remove <strong>{item.short_code}</strong> and its click data.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(item.short_code)} disabled={deletingCode === item.short_code} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                                {deletingCode === item.short_code ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : null}
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Index;
