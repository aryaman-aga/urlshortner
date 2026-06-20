import { useState, type FormEvent } from "react";
import { Link, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import IOSDatePicker from "@/components/IOSDatePicker";
import { shortenUrl, ShortenResponse } from "@/lib/api";
import { toast } from "@/hooks/use-toast";

interface ShortenFormProps {
  onResult: (result: ShortenResponse) => void;
}

const ShortenForm = ({ onResult }: ShortenFormProps) => {
  const [url, setUrl] = useState("");
  const [alias, setAlias] = useState("");
  const [expiry, setExpiry] = useState("");
  const [loading, setLoading] = useState(false);
  const [showOptions, setShowOptions] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    try {
      const result = await shortenUrl({
        url: url.trim(),
        ...(alias.trim() && { custom_alias: alias.trim() }),
        ...(expiry && { expiry }),
      });
      onResult(result);
      setUrl("");
      setAlias("");
      setExpiry("");
      toast({ title: "URL shortened successfully!", description: "Your short link is ready." });
    } catch (err: any) {
      const message = err.response?.data?.error || err.response?.data?.message || "Something went wrong. Please try again.";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="relative">
        <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="url"
          placeholder="Paste your long URL here..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          className="pl-10 h-12 text-base"
        />
      </div>

      <button
        type="button"
        onClick={() => setShowOptions(!showOptions)}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        {showOptions ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        Advanced options
      </button>

      {showOptions && (
        <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-200">
          <div>
            <Label htmlFor="alias" className="text-sm text-muted-foreground">Custom alias</Label>
            <Input
              id="alias"
              placeholder="my-custom-link"
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="expiry" className="text-sm text-muted-foreground">Expiry date</Label>
            <IOSDatePicker value={expiry} onChange={setExpiry} />
          </div>
        </div>
      )}

      <Button type="submit" className="w-full h-12 text-base font-semibold" disabled={loading || !url.trim()}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
        {loading ? "Shortening..." : "Shorten URL"}
      </Button>
    </form>
  );
};

export default ShortenForm;
