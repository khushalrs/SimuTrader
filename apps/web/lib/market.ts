"use client"

const DEFAULT_API_BASE_URL = "http://localhost:8000"
const isServer = typeof window === "undefined"
// @ts-ignore
const API_BASE_URL = isServer
    // @ts-ignore
    ? process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL
    // @ts-ignore
    : process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL

export interface MarketBarOut {
    date: string
    symbol: string
    currency: string
    exchange: string
    open?: number | null
    high?: number | null
    low?: number | null
    close?: number | null
    volume?: number | null
}

export interface MarketCoverageOut {
    symbol: string
    first_date: string
    last_date: string
    rows: number
    missing_ratio?: number | null
}

export interface MarketSnapshotOut {
    symbol: string
    last_date: string
    last_close: number
    return_1w?: number | null
    return_1m?: number | null
    return_3m?: number | null
    return_1y?: number | null
    recent_vol_20d?: number | null
    median_vol_1y?: number | null
    meta?: any
}

// In-memory cache to prevent spamming backend during navigation and lab updates
const cache = new Map<string, { timestamp: number, data: any }>();
const pendingRequests = new Map<string, Promise<any>>();
const CACHE_TTL_MS = 60000; // 1 minute

function getCached<T>(key: string): T | null {
    const entry = cache.get(key);
    if (entry && (Date.now() - entry.timestamp) < CACHE_TTL_MS) {
        return entry.data as T;
    }
    return null;
}

function setCached(key: string, data: any) {
    cache.set(key, { timestamp: Date.now(), data });
}

async function deduplicatedFetch<T>(url: URL, cacheKey: string): Promise<T> {
    const cached = getCached<T>(cacheKey);
    if (cached) return cached;

    if (pendingRequests.has(cacheKey)) {
        return pendingRequests.get(cacheKey) as Promise<T>;
    }

    const promise = (async () => {
        try {
            const res = await fetch(url.toString(), { cache: "no-store" });
            if (!res.ok) {
                console.error(`Failed to fetch ${url.pathname}: ${res.status} ${res.statusText}`);
                throw new Error(`${res.status} ${res.statusText}`);
            }
            const data = await res.json();
            setCached(cacheKey, data);
            return data;
        } finally {
            pendingRequests.delete(cacheKey);
        }
    })();

    pendingRequests.set(cacheKey, promise);
    return promise;
}

export async function getMarketBars(
    symbols: string[],
    startDate?: string,
    endDate?: string,
    fields: string = "close",
    calendar: string = "GLOBAL",
    missingBar: string = "FORWARD_FILL",
    maxPoints?: number
): Promise<MarketBarOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/market/bars`)
        url.searchParams.append("symbols", symbols.join(","))
        if (startDate) url.searchParams.append("start_date", startDate)
        if (endDate) url.searchParams.append("end_date", endDate)
        if (fields) url.searchParams.append("fields", fields)
        if (calendar) url.searchParams.append("calendar", calendar)
        if (missingBar) url.searchParams.append("missing_bar", missingBar)
        if (maxPoints != null) url.searchParams.append("max_points", maxPoints.toString())

        const cacheKey = `bars_${url.toString()}`;
        return await deduplicatedFetch<MarketBarOut[]>(url, cacheKey);
    } catch (error) {
        console.error("Error fetching market bars:", error)
        return []
    }
}

export async function getMarketCoverage(
    symbols: string[],
    startDate?: string,
    endDate?: string,
    calendar: string = "GLOBAL"
): Promise<MarketCoverageOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/market/coverage`)
        url.searchParams.append("symbols", symbols.join(","))
        if (startDate) url.searchParams.append("start_date", startDate)
        if (endDate) url.searchParams.append("end_date", endDate)
        if (calendar) url.searchParams.append("calendar", calendar)

        const cacheKey = `coverage_${url.toString()}`;
        return await deduplicatedFetch<MarketCoverageOut[]>(url, cacheKey);
    } catch (error) {
        console.error("Error fetching market coverage:", error)
        return []
    }
}

export async function getMarketSnapshot(
    symbols: string[],
    endDate?: string
): Promise<MarketSnapshotOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/market/snapshot`)
        url.searchParams.append("symbols", symbols.join(","))
        if (endDate) url.searchParams.append("end_date", endDate)

        const cacheKey = `snapshot_${url.toString()}`;
        return await deduplicatedFetch<MarketSnapshotOut[]>(url, cacheKey);
    } catch (error) {
        console.error("Error fetching market snapshot:", error)
        return []
    }
}
