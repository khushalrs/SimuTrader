"use client";

import React, { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MarketSnapshot } from "./MarketSnapshot";
import { AssetSearchSection } from "./AssetSearchSection";
import { MultiSymbolLab } from "./MultiSymbolLab";
import { LazyLoadWrapper } from "./LazyLoadWrapper";

export default function ExplorePage() {
    const [activeTab, setActiveTab] = useState("snapshot");

    return (
        <div className="flex-1 space-y-4 p-8 pt-6">
            <div className="flex items-center justify-between space-y-2">
                <h2 className="text-3xl font-bold tracking-tight">Market Explore</h2>
            </div>
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                <TabsList>
                    <TabsTrigger value="snapshot">Market Snapshot</TabsTrigger>
                    <TabsTrigger value="search">Asset Search</TabsTrigger>
                    <TabsTrigger value="lab">Multi-symbol Lab</TabsTrigger>
                </TabsList>
                
                <TabsContent value="snapshot" className="space-y-4">
                    <LazyLoadWrapper active={activeTab === "snapshot"}>
                        <MarketSnapshot />
                    </LazyLoadWrapper>
                </TabsContent>
                
                <TabsContent value="search" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Asset Search & Detail</CardTitle>
                            <CardDescription>
                                Search for an asset to view its metrics and visualizations.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="min-h-[400px]">
                                <LazyLoadWrapper active={activeTab === "search"}>
                                    <AssetSearchSection />
                                </LazyLoadWrapper>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="lab" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Quant Multi-symbol Lab</CardTitle>
                            <CardDescription>
                                Build a watchlist to compare multiple assets statistically.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="min-h-[400px]">
                                <LazyLoadWrapper active={activeTab === "lab"}>
                                    <MultiSymbolLab />
                                </LazyLoadWrapper>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
