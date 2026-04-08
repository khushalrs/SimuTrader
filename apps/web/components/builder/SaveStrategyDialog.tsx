import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { createStrategy } from "@/lib/api";
import { Save, Loader2, CheckCircle2 } from "lucide-react";

export function SaveStrategyDialog({ config }: { config: any }) {
    const [name, setName] = useState(config.name || "Custom Strategy");
    const [description, setDescription] = useState("");
    const [isSaving, setIsSaving] = useState(false);
    const [savedId, setSavedId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleSave = async () => {
        setIsSaving(true);
        setError(null);
        try {
            const res = await createStrategy({
                name,
                description,
                config
            });
            setSavedId(res.strategy_id);
        } catch (e: any) {
            setError(e.message || "Failed to save strategy");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Dialog>
            <DialogTrigger asChild>
                <Button variant="outline" className="gap-2 shrink-0 border-primary/20 hover:bg-primary/5 text-primary hover:text-primary transition-colors">
                    <Save className="w-4 h-4" />
                    Save Strategy
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Save to Library</DialogTitle>
                    <DialogDescription>
                        Save this configuration to your Strategy Library to instantly re-use it later or benchmark it via the Compare tool.
                    </DialogDescription>
                </DialogHeader>

                {savedId ? (
                    <div className="py-8 flex flex-col items-center justify-center text-center space-y-4">
                        <div className="w-16 h-16 bg-emerald-500/10 rounded-full flex items-center justify-center mb-2">
                            <CheckCircle2 className="w-8 h-8 text-emerald-500 animate-in zoom-in duration-300" />
                        </div>
                        <h3 className="font-bold text-xl text-foreground">Strategy Saved!</h3>
                        <div className="text-sm font-mono tracking-tight bg-secondary px-3 py-1.5 rounded-md text-muted-foreground border border-border/50">
                            ID: {savedId.split('-')[0]}
                        </div>
                    </div>
                ) : (
                    <div className="grid gap-5 py-4">
                        <div className="flex flex-col gap-2.5">
                            <label htmlFor="name" className="text-sm font-semibold tracking-tight text-foreground">
                                Strategy Name
                            </label>
                            <input
                                id="name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                placeholder="e.g. Multi-Asset Trend Following"
                            />
                        </div>
                        <div className="flex flex-col gap-2.5">
                            <label htmlFor="description" className="text-sm font-semibold tracking-tight text-foreground flex items-center justify-between">
                                Description 
                                <span className="text-xs text-muted-foreground font-normal">Optional</span>
                            </label>
                            <textarea
                                id="description"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
                                placeholder="Describe the hypotheses, universe selections, and parameter logic..."
                            />
                        </div>
                        {error && (
                            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                                <p className="text-sm text-destructive font-medium">{error}</p>
                            </div>
                        )}
                    </div>
                )}
                
                {!savedId && (
                    <DialogFooter className="mt-2">
                        <Button type="button" onClick={handleSave} disabled={isSaving || !name.trim()} className="w-full sm:w-auto">
                            {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                            Save to Library
                        </Button>
                    </DialogFooter>
                )}
            </DialogContent>
        </Dialog>
    )
}
