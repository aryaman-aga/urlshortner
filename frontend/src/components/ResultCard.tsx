import { useState } from "react";
import { Copy, Check, ExternalLink } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/button";
import { ShortenResponse } from "@/lib/api";
import { toast } from "@/hooks/use-toast";

interface ResultCardProps {
  result: ShortenResponse;
}

const ResultCard = ({ result }: ResultCardProps) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result.short_url);
    setCopied(true);
    toast({ title: "Copied!", description: "Short URL copied to clipboard." });
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border bg-accent/40 p-5 animate-in fade-in slide-in-from-bottom-4 duration-300">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Your short link</p>
      
      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <a
            href={result.short_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-lg font-semibold text-primary hover:underline truncate block"
          >
            {result.short_url}
          </a>
        </div>
        <Button variant="outline" size="icon" onClick={handleCopy} className="shrink-0">
          {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
        </Button>
        <Button variant="outline" size="icon" asChild className="shrink-0">
          <a href={result.short_url} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>
      </div>
      <div className="mt-4 flex flex-col items-center gap-3">
        <div className="bg-card rounded-lg p-3 border">
          <QRCodeSVG id="qr-code" value={result.short_url} size={140} />
        </div>

        <p className="text-xs text-muted-foreground">Scan to open</p>

        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            const svg = document.getElementById("qr-code");
            const serializer = new XMLSerializer();
            const source = serializer.serializeToString(svg);
            const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
            const url = URL.createObjectURL(blob);

            const link = document.createElement("a");
            link.href = url;
            link.download = "qr-code.svg";
            link.click();
          }}
        >
          Download QR
        </Button>
      </div>
    </div>
  );
};

export default ResultCard;
