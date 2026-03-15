"use client";

import React, { useState, useEffect } from "react";
import { searchAssets, AssetOut } from "@/lib/api";
import { Loader2, Search } from "lucide-react";

interface AssetSearchProps {
    onSelectAsset: (asset: AssetOut) => void;
    placeholder?: string;
    className?: string;
}

export function AssetSearch({ onSelectAsset, placeholder = "Search instruments (e.g. AAPL)...", className = "" }: AssetSearchProps) {
    const [symbolInput, setSymbolInput] = useState("");
    const [debouncedInput, setDebouncedInput] = useState("");
    const [results, setResults] = useState<AssetOut[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);

    // Debounce
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedInput(symbolInput);
        }, 300);
        return () => clearTimeout(timer);
    }, [symbolInput]);

    // Search Assets
    useEffect(() => {
        if (!debouncedInput.trim()) {
            setResults([]);
            setIsSearching(false);
            return;
        }
        let active = true;
        setIsSearching(true);
        searchAssets(debouncedInput.trim()).then(res => {
            if (active) {
                setResults(res);
                setIsSearching(false);
            }
        }).catch(() => {
            if (active) setIsSearching(false);
        });

        return () => { active = false; };
    }, [debouncedInput]);

    const handleSelect = (asset: AssetOut) => {
        setSymbolInput("");
        setShowDropdown(false);
        onSelectAsset(asset);
    };

    return (
        <div className={`relative ${className}`}>
            <div className="relative w-full">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <input
                    type="text"
                    placeholder={placeholder}
                    className="flex h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    value={symbolInput}
                    onChange={e => {
                        setSymbolInput(e.target.value);
                        setShowDropdown(true);
                    }}
                    onFocus={() => setShowDropdown(true)}
                    onBlur={() => {
                        // Small delay to allow click on dropdown to fire handleSelect
                        setTimeout(() => setShowDropdown(false), 200);
                    }}
                />
            </div>

            {showDropdown && symbolInput.trim() && (
                <div className="absolute top-12 left-0 w-full bg-background border border-border shadow-lg z-50 rounded-md max-h-60 overflow-y-auto">
                    {isSearching ? (
                        <div className="p-4 flex items-center justify-center text-muted-foreground text-sm">
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Searching...
                        </div>
                    ) : results.length > 0 ? (
                        <ul className="py-1 text-sm">
                            {results.map((r, i) => (
                                <li
                                    key={`${r.symbol}-${i}`}
                                    className="px-4 py-2 hover:bg-muted cursor-pointer flex justify-between items-center"
                                    onClick={() => handleSelect(r)}
                                >
                                    <span>
                                        <span className="font-semibold text-foreground mr-2">{r.symbol}</span>
                                        <span className="text-muted-foreground">{r.name}</span>
                                    </span>
                                    <span className="text-xs bg-muted-foreground/20 text-muted-foreground px-1.5 py-0.5 rounded">
                                        {r.asset_class}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="p-4 text-muted-foreground text-sm text-center">
                            No matches found for "{debouncedInput}"
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
