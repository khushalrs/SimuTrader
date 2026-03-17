import { MarketBarOut } from "./market";

// Type definitions internally used for math
interface ReturnSeries {
    date: string;
    returns: number;
}

export function computeReturns(bars: MarketBarOut[]): ReturnSeries[] {
    if (bars.length < 2) return [];

    const returns: ReturnSeries[] = [];
    for (let i = 1; i < bars.length; i++) {
        const prev = bars[i - 1].close;
        const curr = bars[i].close;

        if (prev != null && prev !== 0 && curr != null) {
            returns.push({
                date: bars[i].date,
                returns: (curr / prev) - 1,
            });
        }
    }
    return returns;
}

export function normalizePerformance(bars: MarketBarOut[], baseValue: number = 100) {
    if (bars.length === 0) return [];
    const firstClose = bars[0].close;
    if (firstClose == null || firstClose === 0) return [];

    return bars.map(b => ({
        date: b.date,
        symbol: b.symbol,
        value: b.close != null ? (b.close / firstClose) * baseValue : null
    }));
}

export function computeDrawdown(bars: MarketBarOut[]) {
    let maxHigh = -Infinity;
    return bars.map(b => {
        if (b.close == null) {
            return { date: b.date, symbol: b.symbol, drawdown: 0 };
        }
        
        if (b.close > maxHigh) {
            maxHigh = b.close;
        }

        const drawdown = (maxHigh > 0) ? (b.close / maxHigh) - 1 : 0;
        return {
            date: b.date,
            symbol: b.symbol,
            drawdown
        };
    });
}

function mean(arr: number[]): number {
    return arr.reduce((a, b) => a + b, 0) / arr.length;
}

export function rollingVol(returns: number[], window: number = 20): number[] {
    const vols: number[] = [];
    for (let i = window - 1; i < returns.length; i++) {
        const slice = returns.slice(i - window + 1, i + 1);
        const m = mean(slice);
        const variance = slice.reduce((a, b) => a + Math.pow(b - m, 2), 0) / slice.length;
        const annVol = Math.sqrt(variance) * Math.sqrt(252);
        vols.push(annVol);
    }
    return vols;
}

// Map dates to vol values
export function rollingVolSeries(bars: MarketBarOut[], window: number = 20) {
    const retSeries = computeReturns(bars);
    const rets = retSeries.map(r => r.returns);
    const vols = rollingVol(rets, window);
    // vols array starts at index `window - 1` with respect to returns array
    // meaning the first vol coincides with the `window`th return (which is the `window + 1`th bar)
    
    const results = [];
    for (let i = 0; i < vols.length; i++) {
        results.push({
            date: retSeries[i + window - 1].date,
            volatility: vols[i]
        });
    }
    return results;
}

export function correlation(x: number[], y: number[]): number {
    if (x.length !== y.length || x.length === 0) return NaN;

    const meanX = mean(x);
    const meanY = mean(y);

    let num = 0;
    let denX = 0;
    let denY = 0;

    for (let i = 0; i < x.length; i++) {
        const dx = x[i] - meanX;
        const dy = y[i] - meanY;
        num += dx * dy;
        denX += dx * dx;
        denY += dy * dy;
    }

    if (denX === 0 || denY === 0) return 0;
    return num / Math.sqrt(denX * denY);
}

export function correlationMatrix(returnsBySymbol: Record<string, number[]>): Record<string, Record<string, number>> {
    const symbols = Object.keys(returnsBySymbol);
    const matrix: Record<string, Record<string, number>> = {};

    for (const s1 of symbols) {
        matrix[s1] = {};
        for (const s2 of symbols) {
            if (s1 === s2) {
                matrix[s1][s2] = 1.0;
            } else if (matrix[s2] && matrix[s2][s1] !== undefined) {
                // Symmetric
                matrix[s1][s2] = matrix[s2][s1];
            } else {
                matrix[s1][s2] = correlation(returnsBySymbol[s1], returnsBySymbol[s2]);
            }
        }
    }
    return matrix;
}

export function monthlyReturnsHeatmap(bars: MarketBarOut[]): { year: number, month: number, return: number }[] {
    if (bars.length === 0) return [];
    
    // Group closes by Year-Month
    const monthlyCloses: Record<string, number> = {};
    for (const b of bars) {
        if (!b.date || b.close == null) continue;
        const [y, m] = b.date.split("-");
        const key = `${y}-${m}`;
        // The last available close of the month overwrites previous ones
        monthlyCloses[key] = b.close;
    }

    const sortedKeys = Object.keys(monthlyCloses).sort();
    const monthlyReturns = [];

    for (let i = 1; i < sortedKeys.length; i++) {
        const prevKey = sortedKeys[i - 1];
        const currKey = sortedKeys[i];
        
        const prevClose = monthlyCloses[prevKey];
        const currClose = monthlyCloses[currKey];
        
        if (prevClose && currClose) {
            const [y, m] = currKey.split("-");
            monthlyReturns.push({
                year: parseInt(y, 10),
                month: parseInt(m, 10),
                return: (currClose / prevClose) - 1
            });
        }
    }
    
    return monthlyReturns;
}

/**
 * Downsamples data to roughly `targetLength` points using a simple interval step.
 * This prevents Recharts from rendering thousands of nodes.
 */
export function downsampleData<T>(data: T[], targetLength: number = 200): T[] {
    if (data.length <= targetLength) return data;
    
    // Always keep the first and last points, and interval step through the rest
    const step = Math.ceil((data.length - 2) / (targetLength - 2));
    const result: T[] = [data[0]];
    
    for (let i = step; i < data.length - 1; i += step) {
        result.push(data[i]);
    }
    
    result.push(data[data.length - 1]);
    return result;
}
