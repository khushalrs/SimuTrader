export interface PageHelpContent {
    slug: string
    title: string
    oneLiner: string
    howItWorksSteps: string[]
    version: number
}

export interface FieldHelpContent {
    fieldKey: string
    label: string
    description: string
    example: string
    relatedPageSlug: string
}

export interface GlossaryTerm {
    key: string
    term: string
    definition: string
    formula?: string
    category: "Metrics" | "Validation" | "Execution" | "Simulation"
}

export const PAGES: Record<string, PageHelpContent> = {
    home: {
        slug: "home",
        title: "SimuTrader Overview",
        oneLiner: "Portfolio-grade backtesting, quantitative strategy simulation, and market data diagnostics.",
        howItWorksSteps: [
            "Explore pre-built quantitative strategy presets or launch the interactive Builder.",
            "Run historical backtests across customizable universe and friction parameters.",
            "Analyze risk metrics, cost breakdowns, and portfolio allocation in real-time."
        ],
        version: 1
    },
    playground: {
        slug: "playground",
        title: "Simulation Playground",
        oneLiner: "Test and compare quantitative strategy presets with zero configuration required.",
        howItWorksSteps: [
            "Select from preset strategies like Trend Following, Mean Reversion, or Risk Parity.",
            "Instantly trigger backtest runs and inspect equity curves.",
            "Clone any preset into the Strategy Builder for customization."
        ],
        version: 1
    },
    build_page: {
        slug: "build_page",
        title: "Strategy Builder Studio",
        oneLiner: "Design, configure, and validate custom quantitative trading strategies step by step.",
        howItWorksSteps: [
            "Define Asset Universe selection rules and symbol filters.",
            "Configure Strategy Logic (factor signals, target weight rules, rebalance frequencies).",
            "Set Execution Realism parameters (slippage bps, commissions, tax regimes, and borrow rates).",
            "Run preflight data validation before launching the simulation."
        ],
        version: 1
    },
    explore: {
        slug: "explore",
        title: "Market Data & Quality Diagnostics",
        oneLiner: "Inspect asset coverage, missing bar policies, and market data snapshot integrity.",
        howItWorksSteps: [
            "Search and inspect historical price series across global equities and ETFs.",
            "Verify data quality, gaps, and missing bar interpolation policies.",
            "Audit live quote snapshots and reference price feeds."
        ],
        version: 1
    },
    research: {
        slug: "research",
        title: "Research Lab & Optimization Studio",
        oneLiner: "Execute hyperparameter grid sweeps, in-sample/out-of-sample splits, and Monte Carlo resampling.",
        howItWorksSteps: [
            "Scaffold parameter grid sweeps across strategy variables.",
            "Monitor live progress and child worker dispatch.",
            "Analyze 2D parameter heatmaps to distinguish true plateaus from overfit spikes.",
            "Evaluate In-Sample vs Out-of-Sample degradation and Monte Carlo tail safety."
        ],
        version: 1
    },
    compare: {
        slug: "compare",
        title: "Multi-Strategy Comparison",
        oneLiner: "Overlay equity curves, compare risk metrics, and evaluate drawdown trade-offs side by side.",
        howItWorksSteps: [
            "Select multiple backtest runs from your history.",
            "Compare Sharpe, CAGR, Max Drawdown, and Turnover side by side.",
            "Overlay normalized equity curves to evaluate relative outperformance."
        ],
        version: 1
    },
    runs: {
        slug: "runs",
        title: "Simulation Runs History",
        oneLiner: "Browse, filter, and manage all historical backtest simulation runs.",
        howItWorksSteps: [
            "Filter runs by status (Succeeded, Running, Failed) or strategy name.",
            "Inspect high-level performance metrics (Sharpe, CAGR, Max DD).",
            "Click any run row to open its comprehensive analytical dashboard."
        ],
        version: 1
    },
    run_detail: {
        slug: "run_detail",
        title: "Run Dashboard & Inspector",
        oneLiner: "Deep dive into performance curves, trade fills, cost waterfalls, and decision traces.",
        howItWorksSteps: [
            "Analyze Performance, Risk, Exposure, Costs, Monthly Heatmaps, and Rolling Metrics.",
            "Inspect trade executions in Fills, Portfolio Replay Scrubber, or Pipeline Timeline.",
            "Click any fill to open the 'Why This Trade?' Inspector for signal ranks and tax lot accounting."
        ],
        version: 1
    },
    strategies: {
        slug: "strategies",
        title: "Strategy Library & Templates",
        oneLiner: "Manage saved strategy configurations, versions, and reusable templates.",
        howItWorksSteps: [
            "Browse your custom saved strategies and pre-built system presets.",
            "Edit, fork, or clone strategy configs directly.",
            "Launch new simulation runs from any strategy template."
        ],
        version: 1
    },
    guide: {
        slug: "guide",
        title: "Documentation & Technical Glossary",
        oneLiner: "Comprehensive sitemap, feature area guides, and technical quantitative definitions.",
        howItWorksSteps: [
            "Browse feature area walkthroughs for Builder, Research Lab, and Run Analytics.",
            "Use deep links to jump directly to specific metrics or policies.",
            "Lookup formal mathematical definitions and formula references in the Glossary."
        ],
        version: 1
    }
}

export const GLOSSARY: GlossaryTerm[] = [
    {
        key: "sharpe",
        term: "Sharpe Ratio",
        definition: "A measure of risk-adjusted return, calculated as excess annual return over the risk-free rate divided by annual volatility.",
        formula: "\\text{Sharpe} = \\frac{R_p - R_f}{\\sigma_p}",
        category: "Metrics"
    },
    {
        key: "sortino",
        term: "Sortino Ratio",
        definition: "A variation of the Sharpe ratio that isolates downside volatility, penalizing only negative returns.",
        formula: "\\text{Sortino} = \\frac{R_p - R_f}{\\sigma_{\\text{down}}}",
        category: "Metrics"
    },
    {
        key: "var_cvar",
        term: "Value at Risk (VaR / CVaR)",
        definition: "VaR estimates maximum expected loss at a given confidence level (e.g. 95%). CVaR (Conditional VaR / Expected Shortfall) measures average loss in tail events beyond VaR.",
        formula: "\\text{CVaR}_{\\alpha} = E[X \\mid X \\le \\text{VaR}_{\\alpha}]",
        category: "Metrics"
    },
    {
        key: "turnover",
        term: "Portfolio Turnover",
        definition: "The percentage of portfolio holdings traded over a period, measuring trading intensity and friction impact.",
        formula: "\\text{Turnover} = \\frac{\\sum |\\text{Trades}|}{2 \\times \\text{Average Equity}}",
        category: "Metrics"
    },
    {
        key: "drawdown",
        term: "Max Drawdown",
        definition: "The peak-to-trough decline during a specific period, representing maximum historical loss before a new peak.",
        formula: "\\text{Drawdown}_t = \\frac{E_t - \\max_{\\tau \\le t} E_T}{\\max_{\\tau \\le t} E_T}",
        category: "Metrics"
    },
    {
        key: "beta",
        term: "Beta (Sensitivity)",
        definition: "A measure of strategy volatility relative to the benchmark market index.",
        formula: "\\beta = \\frac{\\text{Cov}(R_p, R_m)}{\\text{Var}(R_m)}",
        category: "Metrics"
    },
    {
        key: "is_oos",
        term: "IS / OOS (In-Sample / Out-of-Sample)",
        definition: "Splitting historical data into training (In-Sample) and validation (Out-of-Sample) windows to evaluate overfit degradation.",
        category: "Validation"
    },
    {
        key: "monte_carlo",
        term: "Monte Carlo Resampling",
        definition: "A simulation technique that bootstraps daily returns to generate hundreds of synthetic equity paths, surfacing confidence bands and tail risk.",
        category: "Validation"
    },
    {
        key: "robustness",
        term: "Parameter Robustness",
        definition: "Assessing whether strategy performance forms a smooth plateau across parameter variations rather than a fragile single-point overfit spike.",
        category: "Validation"
    },
    {
        key: "friction_bps",
        term: "Commission & Slippage (bps)",
        definition: "Friction costs modeled as basis points (1 bps = 0.01%) applied to order notionals to simulate market impact and execution cost.",
        category: "Execution"
    },
    {
        key: "missing_bar_policy",
        term: "Missing-Bar Policy",
        definition: "Rules for handling market data gaps (e.g. forward fill previous price, drop non-trading days, or alert data quality gap).",
        category: "Simulation"
    },
    {
        key: "seed_snapshot",
        term: "Seed & Data Snapshot",
        definition: "Cryptographic hash locking data snapshot and random seed to guarantee 100% deterministic, reproducible backtest runs.",
        category: "Simulation"
    }
]

export const FIELDS: FieldHelpContent[] = [
    {
        fieldKey: "universe.top_n",
        label: "Top N Assets",
        description: "Number of top-ranked assets selected from the universe per rebalance.",
        example: "5",
        relatedPageSlug: "build_page"
    },
    {
        fieldKey: "rebalance.frequency",
        label: "Rebalance Frequency",
        description: "How often position weights are recalculated and rebalanced (DAILY, WEEKLY, MONTHLY).",
        example: "WEEKLY",
        relatedPageSlug: "build_page"
    },
    {
        fieldKey: "execution.slippage_bps",
        label: "Slippage (bps)",
        description: "Execution price penalty in basis points.",
        example: "5 bps",
        relatedPageSlug: "build_page"
    }
]
