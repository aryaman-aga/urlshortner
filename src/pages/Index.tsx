import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Scissors } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import ThemeToggle from "@/components/ThemeToggle";
import ShortenForm from "@/components/ShortenForm";
import ResultCard from "@/components/ResultCard";
import StatsCard from "@/components/StatsCard";
import { listUrls, ShortenResponse, type UrlItem } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { clearAuth } from "@/lib/auth";

const Index = () => {
  const navigate = useNavigate();
  const [result, setResult] = useState<ShortenResponse | null>(null);
  const [urls, setUrls] = useState<UrlItem[]>([]);
  const [urlsLoading, setUrlsLoading] = useState(false);

  const handleLogout = () => {
    clearAuth();
    navigate("/login", { replace: true });
  };

  const loadUrls = async () => {
    setUrlsLoading(true);
    try {
      const data = await listUrls({ limit: 100, skip: 0 });
      setUrls(data.items);
    } finally {
      setUrlsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b">
        <div className="container max-w-3xl mx-auto flex items-center justify-between py-4 px-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
              <Scissors className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold tracking-tight">Sniplink</span>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex items-start justify-center px-4 py-12 md:py-20">
        <div className="w-full max-w-xl space-y-8">
          {/* Hero text */}
          <div className="text-center space-y-2">
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
              Shorten your links,{" "}
              <span className="text-primary">amplify</span> your reach
            </h1>
            <p className="text-muted-foreground text-base md:text-lg">
              Create short, memorable links in seconds. Track clicks and manage expiry.
            </p>
          </div>

          {/* Shortener card */}
          <Card className="shadow-lg border-border/60">
            <CardContent className="p-6 space-y-5">
              <ShortenForm onResult={setResult} />
              {result && <ResultCard result={result} />}
            </CardContent>
          </Card>

          {/* Analytics */}
          <Card className="shadow-sm border-border/60">
            <CardContent className="p-6">
              <StatsCard />
            </CardContent>
          </Card>

          {/* Database */}
          <Card className="shadow-sm border-border/60">
            <CardContent className="p-6 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">My Links</h2>
                  <p className="text-sm text-muted-foreground">Reads from your database</p>
                </div>
                <Button variant="secondary" onClick={loadUrls} disabled={urlsLoading}>
                  {urlsLoading ? "Loading..." : "Refresh"}
                </Button>
              </div>

              <div className="rounded-xl border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Short</TableHead>
                      <TableHead>Original URL</TableHead>
                      <TableHead className="text-right">Clicks</TableHead>
                      <TableHead>Expiry</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {urls.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="text-sm text-muted-foreground">
                          Click Refresh to load your links.
                        </TableCell>
                      </TableRow>
                    ) : (
                      urls.map((item) => (
                        <TableRow key={item.short_code}>
                          <TableCell className="font-medium">
                            <a
                              href={item.short_url ?? `/${item.short_code}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary hover:underline"
                            >
                              {item.short_code}
                            </a>
                          </TableCell>
                          <TableCell className="max-w-[280px] truncate">
                            <a
                              href={item.original_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary hover:underline"
                              title={item.original_url}
                            >
                              {item.original_url}
                            </a>
                          </TableCell>
                          <TableCell className="text-right tabular-nums">{item.clicks}</TableCell>
                          <TableCell>
                            {item.expiry ? new Date(item.expiry).toLocaleString() : "Never"}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {/* Footer */}
          <p className="text-center text-xs text-muted-foreground">
            Built with React & Tailwind CSS
          </p>
        </div>
      </main>
    </div>
  );
};

export default Index;
