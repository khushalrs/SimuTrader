"use client";

import React, { useState } from "react";
import { AssetSearch } from "./AssetSearch";
import { AssetOut } from "@/lib/api";
import dynamic from "next/dynamic";

const AssetDetailDrawer = dynamic(() => import("./AssetDetailDrawer").then(mod => mod.AssetDetailDrawer), { ssr: false });

export function AssetSearchSection() {
    const [selectedAsset, setSelectedAsset] = useState<AssetOut | null>(null);
    const [isDrawerOpen, setIsDrawerOpen] = useState(false);

    const handleSelectAsset = (asset: AssetOut) => {
        setSelectedAsset(asset);
        setIsDrawerOpen(true);
    };

    return (
        <div className="flex flex-col space-y-4">
            <div className="max-w-xl w-full">
                <AssetSearch 
                    onSelectAsset={handleSelectAsset} 
                    placeholder="Search an asset to view details (e.g. AAPL, BTC, INFY)..."
                />
            </div>
            
            <div className="h-[400px] flex items-center justify-center text-muted-foreground border border-dashed rounded-lg bg-muted/20">
                {!selectedAsset ? (
                    <p>Search and select an asset to view historical performance and analytics.</p>
                ) : (
                    <div className="text-center">
                        <p className="text-lg font-medium text-foreground mb-2">Last Viewed: {selectedAsset.symbol}</p>
                        <p className="text-sm">Drawer handles the asset drilldown.</p>
                    </div>
                )}
            </div>

            {selectedAsset && (
                <AssetDetailDrawer 
                    asset={selectedAsset} 
                    open={isDrawerOpen} 
                    onOpenChange={setIsDrawerOpen} 
                />
            )}
        </div>
    );
}
