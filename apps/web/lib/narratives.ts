import { MarketSnapshotOut } from "./market";
import { correlationMatrix } from "./analytics";

export function getLeaderLaggardNarrative(snapshots: MarketSnapshotOut[]): {
    leader: MarketSnapshotOut | null;
    laggard: MarketSnapshotOut | null;
    dispersion: number;
    narrative: string;
} {
    if (!snapshots || snapshots.length === 0) {
        return { leader: null, laggard: null, dispersion: 0, narrative: "Not enough data." };
    }

    const validSnapshots = snapshots.filter(s => s.return_1y != null);
    if (validSnapshots.length < 2) {
        return { leader: validSnapshots[0] || null, laggard: null, dispersion: 0, narrative: "Not enough comparative data." };
    }

    const sortedBy1Y = [...validSnapshots].sort((a, b) => (b.return_1y || 0) - (a.return_1y || 0));
    const leader = sortedBy1Y[0];
    const laggard = sortedBy1Y[sortedBy1Y.length - 1];
    
    const leadRet = leader.return_1y || 0;
    const lagRet = laggard.return_1y || 0;
    const dispersion = leadRet - lagRet;

    const narrative = `Leader is ${leader.symbol} (+${(leadRet * 100).toFixed(2)}%), outperforming laggard ${laggard.symbol} (${lagRet > 0 ? '+' : ''}${(lagRet * 100).toFixed(2)}%) by ${(dispersion * 100).toFixed(1)}%.`;

    return { leader, laggard, dispersion, narrative };
}

export function getRiskRegimeNarrative(snapshots: MarketSnapshotOut[]): string {
    if (!snapshots || snapshots.length === 0) return "Unknown risk regime.";

    // Simple market cap weighted or average vol vs historical to define 'regime'
    let elevatedCount = 0;
    let totalCount = 0;

    for (const s of snapshots) {
        if (s.recent_vol_20d != null && s.median_vol_1y != null) {
            totalCount++;
            if (s.recent_vol_20d > s.median_vol_1y * 1.1) {
                // 10% above median is 'elevated'
                elevatedCount++;
            }
        }
    }

    if (totalCount === 0) return "Risk regime data unavailable.";

    const ratio = elevatedCount / totalCount;
    if (ratio > 0.5) return "High Risk Regime: Short term volatility is elevated above historical medians across the basket.";
    else if (ratio < 0.2) return "Low Risk Regime: Volatility is subdued compared to rolling 1Y medians.";
    return "Neutral Risk Regime: Volatility is trending near historical medians.";
}

export function getDiversificationSummary(corrMatrix: Record<string, Record<string, number>>): string {
    const symbols = Object.keys(corrMatrix);
    if (symbols.length < 2) return "Not enough assets to measure diversification.";

    let totalCorr = 0;
    let pairsCount = 0;
    let lowestPair = { s1: "", s2: "", corr: Infinity };
    
    for (let i = 0; i < symbols.length; i++) {
        for (let j = i + 1; j < symbols.length; j++) {
            const s1 = symbols[i];
            const s2 = symbols[j];
            const corr = corrMatrix[s1][s2];
            
            if (corr !== undefined && !Number.isNaN(corr)) {
                totalCorr += corr;
                pairsCount++;
                if (corr < lowestPair.corr) {
                    lowestPair = { s1, s2, corr };
                }
            }
        }
    }

    if (pairsCount === 0) return "No valid correlations found.";

    const avgCorr = totalCorr / pairsCount;
    
    let state = "moderate";
    if (avgCorr > 0.6) state = "weak (high expected correlation)";
    else if (avgCorr < 0.2) state = "strong (low expected correlation)";
    
    return `Average basket correlation is ${(avgCorr).toFixed(2)} indicating ${state} diversification. The strongest diversifier pair is ${lowestPair.s1} & ${lowestPair.s2} (${lowestPair.corr.toFixed(2)}).`;
}
