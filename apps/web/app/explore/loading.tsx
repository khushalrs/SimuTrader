import React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default function ExploreLoading() {
    return (
        <div className="flex-1 space-y-6 p-8 pt-6">
            <div className="flex items-center justify-between space-y-2">
                <Skeleton className="h-9 w-[250px]" />
            </div>

            {/* Tabs Skeleton */}
            <div className="flex space-x-2 border-b pb-4">
                <Skeleton className="h-8 w-[150px] rounded-sm" />
                <Skeleton className="h-8 w-[120px] rounded-sm" />
                <Skeleton className="h-8 w-[140px] rounded-sm" />
            </div>

            {/* Top Cards Skeleton */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6 pl-2 pr-2">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Card key={i}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <Skeleton className="h-4 w-[60px]" />
                        </CardHeader>
                        <CardContent>
                            <Skeleton className="h-6 w-[80px] mb-2" />
                            <Skeleton className="h-3 w-[120px]" />
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Main Chart Skeleton */}
            <div className="grid gap-6 grid-cols-1 md:grid-cols-3 mt-6">
                <Card className="col-span-2">
                    <CardHeader>
                        <Skeleton className="h-6 w-[200px]" />
                        <Skeleton className="h-4 w-[300px] mt-2" />
                    </CardHeader>
                    <CardContent>
                        <Skeleton className="h-[400px] w-full mt-4" />
                    </CardContent>
                </Card>
                <Card className="col-span-1">
                    <CardHeader>
                        <Skeleton className="h-6 w-[150px]" />
                        <Skeleton className="h-4 w-[200px] mt-2" />
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Skeleton className="h-[80px] w-full" />
                        <Skeleton className="h-[80px] w-full" />
                        <Skeleton className="h-[80px] w-full" />
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
