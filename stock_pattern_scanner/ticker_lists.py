"""
Ticker lists module: default growth watchlist, S&P 500 / NASDAQ-100 fetching
from Wikipedia with hardcoded fallbacks.
"""

import logging
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DEFAULT GROWTH WATCHLIST (~100 tickers across categories)
# ---------------------------------------------------------------------------

DEFAULT_GROWTH_WATCHLIST: List[str] = [
    # Software / Cloud
    "NOW", "CRM", "WDAY", "TEAM", "DDOG", "SNOW", "NET", "ZS", "CRWD",
    "PANW", "FTNT", "HUBS", "MNDY", "TTD", "BILL", "MDB", "CFLT", "ESTC",
    # Semiconductors
    "NVDA", "AMD", "AVGO", "QCOM", "MRVL", "KLAC", "LRCX", "AMAT", "ASML",
    "TSM", "ON", "NXPI", "MPWR", "SWKS",
    # Consumer / Retail
    "COST", "TJX", "LULU", "CMG", "DECK", "ORLY", "ULTA", "BIRD", "DPZ",
    "CAVA", "WING", "ELF",
    # Healthcare
    "LLY", "NVO", "ISRG", "DXCM", "VEEV", "TMO", "DHR", "SYK", "BSX",
    "PODD", "ALGN", "HOLX",
    # Fintech
    "V", "MA", "PYPL", "SQ", "COIN", "MELI", "NU", "AFRM", "SOFI",
    # Mega-cap Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NFLX",
    # Energy / Industrial
    "NEE", "CEG", "FSLR", "CAT", "DE", "URI", "GE", "UBER", "ABNB",
    # Other growth
    "AXON", "CELH", "DUOL", "RKLB", "TOST", "APP", "IOT", "FOUR",
]

# ---------------------------------------------------------------------------
# S&P 500 FALLBACK (snapshot as of early 2025)
# ---------------------------------------------------------------------------

SP500_FALLBACK: List[str] = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL",
    "A", "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT",
    "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AAL", "AEP",
    "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI",
    "ANSS", "AON", "APA", "AAPL", "AMAT", "APTV", "ACGL", "ADM", "ANET",
    "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY",
    "AXON", "BKR", "BALL", "BAC", "BBWI", "BAX", "BDX", "WRB", "BRK.B",
    "BBY", "BIO", "TECH", "BIIB", "BLK", "BK", "BA", "BKNG", "BWA",
    "BXP", "BSX", "BMY", "AVGO", "BR", "BRO", "BF.B", "BLDR", "BG",
    "CDNS", "CZR", "CPT", "CPB", "COF", "CAH", "KMX", "CCL", "CARR",
    "CTLT", "CAT", "CBOE", "CBRE", "CDW", "CE", "COR", "CNC", "CNP",
    "CF", "CHRW", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD",
    "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS",
    "KO", "CTSH", "CL", "CMCSA", "CMA", "CAG", "COP", "ED", "STZ",
    "CEG", "COO", "CPRT", "GLW", "CTVA", "CSGP", "COST", "CTRA", "CCI",
    "CSX", "CMI", "CVS", "DHI", "DHR", "DRI", "DVA", "DAY", "DECK",
    "DE", "DAL", "XRAY", "DVN", "DXCM", "FANG", "DLR", "DFS", "DG",
    "DLTR", "D", "DPZ", "DOV", "DOW", "DHI", "DTE", "DUK", "DD",
    "EMN", "ETN", "EBAY", "ECL", "EIX", "EW", "EA", "ELV", "LLY",
    "EMR", "ENPH", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR",
    "ESS", "EL", "ETSY", "EG", "EVRG", "ES", "EXC", "EXPE", "EXPD",
    "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FITB",
    "FSLR", "FE", "FIS", "FI", "FLT", "FMC", "F", "FTNT", "FTV",
    "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GEHC", "GEN", "GNRC",
    "GD", "GE", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GS",
    "HAL", "HIG", "HAS", "HCA", "PEAK", "HSIC", "HSY", "HES", "HPE",
    "HLT", "HOLX", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB",
    "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "ILMN", "INCY",
    "IR", "PODD", "INTC", "ICE", "IFF", "IP", "IPG", "INTU", "ISRG",
    "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ",
    "JCI", "JPM", "JNPR", "K", "KVUE", "KDP", "KEY", "KEYS", "KMB",
    "KIM", "KMI", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LW",
    "LVS", "LDOS", "LEN", "LIN", "LYV", "LKQ", "LMT", "L", "LOW",
    "LULU", "LYB", "MTB", "MRO", "MPC", "MKTX", "MAR", "MMC", "MLM",
    "MAS", "MA", "MTCH", "MKC", "MCD", "MCK", "MDT", "MRK", "META",
    "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "MHK",
    "MOH", "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI",
    "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS", "NEE", "NKE",
    "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA",
    "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL",
    "OGN", "OTIS", "PCAR", "PKG", "PANW", "PARA", "PH", "PAYX", "PAYC",
    "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PXD",
    "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU",
    "PEG", "PTC", "PSA", "PHM", "QRVO", "PWR", "QCOM", "DGX", "RL",
    "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY",
    "RHI", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SBAC",
    "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SNA",
    "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK",
    "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP",
    "TGT", "TEL", "TDY", "TFX", "TER", "TSLA", "TXN", "TXT", "TMO",
    "TJX", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN",
    "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH",
    "UHS", "VLO", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VTRS",
    "VICI", "V", "VMC", "WRB", "GWW", "WAB", "WBA", "WMT", "DIS",
    "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WRK",
    "WY", "WMB", "WTW", "GWW", "WYNN", "XEL", "XYL", "YUM", "ZBRA",
    "ZBH", "ZION", "ZTS",
]

# ---------------------------------------------------------------------------
# NASDAQ-100 FALLBACK (snapshot as of early 2025)
# ---------------------------------------------------------------------------

NASDAQ100_FALLBACK: List[str] = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD",
    "AMGN", "AMZN", "ANSS", "ARM", "ASML", "AVGO", "AZN", "BIIB", "BKNG",
    "BKR", "CCEP", "CDNS", "CDW", "CEG", "CHTR", "CMCSA", "COIN", "COST",
    "CPRT", "CRWD", "CSCO", "CSGP", "CTAS", "CTSH", "DASH", "DDOG",
    "DLTR", "DXCM", "EA", "EXC", "FANG", "FAST", "FTNT", "GEHC", "GFS",
    "GILD", "GOOG", "GOOGL", "HON", "IDXX", "ILMN", "INTC", "INTU",
    "ISRG", "KDP", "KHC", "KLAC", "LIN", "LRCX", "LULU", "MAR", "MCHP",
    "MDB", "MDLZ", "MELI", "META", "MNST", "MRNA", "MRVL", "MSFT", "MU",
    "NFLX", "NVDA", "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR",
    "PDD", "PEP", "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SMCI",
    "SNPS", "SPLK", "TEAM", "TMUS", "TSLA", "TTD", "TTWO", "TXN", "VRSK",
    "VRTX", "WBD", "WDAY", "XEL", "ZS",
]

# ---------------------------------------------------------------------------
# Wikipedia fetching helpers
# ---------------------------------------------------------------------------

_SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NASDAQ100_WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"


def get_sp500_tickers() -> List[str]:
    """Fetch S&P 500 tickers from Wikipedia.

    Returns the hardcoded fallback list if the fetch fails for any reason.
    """
    try:
        tables = pd.read_html(_SP500_WIKI_URL)
        # The first table on the page contains the current constituents
        df = tables[0]
        if "Symbol" in df.columns:
            tickers = df["Symbol"].astype(str).str.strip().tolist()
            if len(tickers) >= 400:
                logger.info("Fetched %d S&P 500 tickers from Wikipedia", len(tickers))
                return tickers
        logger.warning(
            "Wikipedia S&P 500 table did not contain expected 'Symbol' column "
            "or had too few rows; using fallback."
        )
    except Exception as exc:
        logger.warning("Failed to fetch S&P 500 tickers from Wikipedia: %s", exc)
    return list(SP500_FALLBACK)


def get_nasdaq100_tickers() -> List[str]:
    """Fetch NASDAQ-100 tickers from Wikipedia.

    Dynamically searches all tables on the page for one that contains a
    'Ticker' column.  Returns the hardcoded fallback list if the fetch fails
    for any reason.
    """
    try:
        tables = pd.read_html(_NASDAQ100_WIKI_URL)
        for table in tables:
            if "Ticker" in table.columns:
                tickers = table["Ticker"].astype(str).str.strip().tolist()
                if len(tickers) >= 90:
                    logger.info(
                        "Fetched %d NASDAQ-100 tickers from Wikipedia", len(tickers)
                    )
                    return tickers
        logger.warning(
            "No Wikipedia NASDAQ-100 table with a 'Ticker' column found; "
            "using fallback."
        )
    except Exception as exc:
        logger.warning("Failed to fetch NASDAQ-100 tickers from Wikipedia: %s", exc)
    return list(NASDAQ100_FALLBACK)
