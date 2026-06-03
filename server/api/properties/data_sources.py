"""
Land Registry — data source functions for the DeepAgent analysis system.

Two endpoints are available, no authentication required:

  1. Price Paid SPARQL
     https://landregistry.data.gov.uk/landregistry/query
     Returns individual transaction records (price, date, address, property type).

  2. House Price Index REST
     https://landregistry.data.gov.uk/data/hpi/region/{region-name}.json
     Returns monthly regional index records (avg price, annual/monthly change).

All external API calls are transparently cached via Redis to reduce latency
and avoid unnecessary repeat requests. See :mod:`server.core.llm_cache`.
"""

from collections import defaultdict
from datetime import date, timedelta

import httpx

from server.core.llm_cache import get_cached_skill_result, set_cached_skill_result

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SPARQL_ENDPOINT = "https://landregistry.data.gov.uk/landregistry/query"
HPI_BASE = "https://landregistry.data.gov.uk/data/hpi/region"


def _default_from_date() -> str:
    """Return date string 3 years ago from today."""
    today = date.today()
    three_ago = today - timedelta(days=3 * 365)
    return three_ago.strftime("%Y-%m-%d")


async def sparql_query(query: str, timeout: int = 60) -> dict:
    """Execute a SPARQL query against the Land Registry endpoint.

    Results are cached in Redis keyed by the SPARQL query string.
    """
    # Check cache first
    cache_params = {"query": query}
    cached = await get_cached_skill_result("sparql_query", cache_params)
    if cached is not None:
        return cached

    # Make the actual HTTP request
    req_params = {"query": query, "output": "json"}
    headers = {"Accept": "application/sparql-results+json"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            SPARQL_ENDPOINT, params=req_params, headers=headers, timeout=timeout
        )
        resp.raise_for_status()
        result = resp.json()

    # Cache the result
    await set_cached_skill_result("sparql_query", cache_params, result)
    return result


async def hpi_get(region: str, params: dict | None = None, timeout: int = 20) -> dict:
    """Fetch HPI data from the Land Registry REST endpoint.

    Results are cached in Redis keyed by region and query parameters.
    """
    cache_params = {
        "region": region,
        "params": params,
    }
    cached = await get_cached_skill_result("hpi_get", cache_params)
    if cached is not None:
        return cached

    url = f"{HPI_BASE}/{region}.json"
    headers = {"Accept": "application/json", "User-Agent": "lr-example/1.0"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()

    await set_cached_skill_result("hpi_get", cache_params, result)
    return result


# ---------------------------------------------------------------------------
# Skill functions
# ---------------------------------------------------------------------------


async def price_paid_transactions(
    postcode_district: str = "GU1",
    limit: int = 10,
) -> list[dict]:
    """Return recent Price Paid transactions for a postcode district.

    Results are cached in Redis keyed by postcode district and limit.
    """
    cache_params = {
        "postcode_district": postcode_district,
        "limit": limit,
    }
    cached = await get_cached_skill_result("price_paid_transactions", cache_params)
    if cached is not None:
        return cached

    from_date = _default_from_date()
    query = f"""
PREFIX ppi:    <http://landregistry.data.gov.uk/def/ppi/>
PREFIX common: <http://landregistry.data.gov.uk/def/common/>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>

SELECT ?price ?date ?street ?postcode ?propertyType WHERE {{
  ?tx a ppi:TransactionRecord ;
      ppi:pricePaid       ?price ;
      ppi:transactionDate ?date ;
      ppi:propertyType    ?propertyType ;
      ppi:propertyAddress ?addr .
  ?addr common:postcode ?postcode ;
        common:street   ?street .
  FILTER(STRSTARTS(STR(?postcode), "{postcode_district} "))
  FILTER(?date >= "{from_date}"^^xsd:date)
}} LIMIT {limit}
"""
    data = await sparql_query(query)
    rows = []
    for b in data["results"]["bindings"]:
        rows.append(
            {
                "price": int(b["price"]["value"]),
                "date": b["date"]["value"],
                "street": b["street"]["value"],
                "postcode": b["postcode"]["value"],
                "propertyType": b["propertyType"]["value"].split("/")[-1],
            }
        )

    await set_cached_skill_result("price_paid_transactions", cache_params, rows)
    return rows


async def top_streets(
    postcode_district: str = "GU1",
    sample: int = 500,
    top_n: int = 5,
) -> list[dict]:
    """Return the top-N streets by average sale price for a postcode district.

    Results are cached in Redis keyed by postcode district, sample size, and top N.
    """
    cache_params = {
        "postcode_district": postcode_district,
        "sample": sample,
        "top_n": top_n,
    }
    cached = await get_cached_skill_result("top_streets", cache_params)
    if cached is not None:
        return cached

    from_date = _default_from_date()
    query = f"""
PREFIX ppi:    <http://landregistry.data.gov.uk/def/ppi/>
PREFIX common: <http://landregistry.data.gov.uk/def/common/>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>

SELECT ?street ?price WHERE {{
  ?tx a ppi:TransactionRecord ;
      ppi:pricePaid       ?price ;
      ppi:transactionDate ?date ;
      ppi:propertyAddress ?addr .
  ?addr common:postcode ?pc ;
        common:street   ?street .
  FILTER(STRSTARTS(STR(?pc), "{postcode_district} "))
  FILTER(?date >= "{from_date}"^^xsd:date)
}} LIMIT {sample}
"""
    data = await sparql_query(query)
    by_street: dict[str, list[float]] = defaultdict(list)
    for b in data["results"]["bindings"]:
        by_street[b["street"]["value"]].append(float(b["price"]["value"]))

    ranked = sorted(
        by_street.items(),
        key=lambda kv: sum(kv[1]) / len(kv[1]),
        reverse=True,
    )[:top_n]

    rows = [
        {
            "street": street,
            "avg_price": round(sum(prices) / len(prices), 2),
            "transactions": len(prices),
        }
        for street, prices in ranked
    ]

    await set_cached_skill_result("top_streets", cache_params, rows)
    return rows


async def regional_hpi(
    region: str = "south-east",
    months: int = 36,
) -> list[dict]:
    """Return the most recent monthly HPI records for a region.

    Results are cached in Redis keyed by region name and month count.
    """
    cache_params = {
        "region": region,
        "months": months,
    }
    cached = await get_cached_skill_result("regional_hpi", cache_params)
    if cached is not None:
        return cached

    data = await hpi_get(region, {"_pageSize": months, "_sort": "-refPeriod"})
    items = data["result"].get("items", [])
    rows = []
    for item in items:
        rows.append(
            {
                "period": item.get("refPeriod"),
                "avg_price": item.get("averagePricesSASM"),
                "annual_change": item.get("annualChange"),
                "monthly_change": item.get("monthlyChange"),
            }
        )

    await set_cached_skill_result("regional_hpi", cache_params, rows)
    return rows
