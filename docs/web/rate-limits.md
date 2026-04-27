# Rate Limits
The WB API has request rate limits. To evenly distribute the load, the `token bucket` algorithm is used. Limits for specific API methods are specified in the documentation.


## For example:

`Request limit` per one seller account for all methods in the Marketplace category:

| Token type |	Period |	Limit |	Interval |	Burst |
|--- | --- | --- | --- | --- |
| Personal |	1 minute |	300 requests |	200 milliseconds |	20 requests |
| Service |	1 minute |	300 requests |	200 milliseconds |	20 requests |
| Base |	1 minute |	150 requests |	200 milliseconds |	10 requests |
| Test |	1 minute |	150 requests |	200 milliseconds |	10 requests |

One request with a response code of `409` is counted as 5 requests

- Period — the time interval during which the maximum number of requests according to the limit can be sent.
- Limit — the maximum number of requests per period. In the example, up to 300 requests can be sent in one minute. Requests should be evenly distributed over time.
- Interval — the time gap for pauses between requests. In the example, it should be `60 seconds/300 requests — 200 milliseconds` or `0.2 seconds`. Use the interval to evenly distribute the sending of requests.
- Burst — the maximum number of requests that can be sent simultaneously, without interval pauses. The allowed burst is also returned in the response header `X-Ratelimit-Remaining`. It appears in all response statuses except for error `429`.
`X-Ratelimit-Remaining` is the number of requests that can currently be sent without pauses. The value of `X-Ratelimit-Remaining` decreases by one after each request. If `X-Ratelimit-Remaining` is `0` and you make the next request without a delay, you will receive a `429` error in response. The value of `X-Ratelimit-Remaining` is restored over time.

> There are cases where one request can count as multiple requests. For example, if you send requests in the Marketplace category, a request with a `409` error will count as 10 requests with other statuses. In such cases, the value of `X-Ratelimit-Remaining` will decrease by 10 units immediately.

If you exceed the request rate limit, you will receive a `429` error. In this case, you need to wait a short period before making the next request. To determine how long you need to wait, use the headers from the `429` response:

- `X-Ratelimit-Retry` — the number of seconds after which you can retry the request. If you attempt it earlier, you will continue to receive a `429` error.
- `X-Ratelimit-Limit` — the maximum allowable burst of requests, which will be replenished after `X-Ratelimit-Reset` seconds.
- `X-Ratelimit-Reset` — the number of seconds after which the allowable burst of requests will be restored to the maximum value specified in `X-Ratelimit-Limit`.

## Response example:

```text
HTTP/1.1 429 Too Many Requests
...
X-Ratelimit-Reset: 29
X-Ratelimit-Retry: 2
...
X-Ratelimit-Limit: 10
```

---

## CLI-side request cache (I-15)

In addition to the header-driven rate limiter, the CLI keeps a local response cache for cacheable read endpoints at `~/.wb-cli/request_cache.db`. The TTL on each entry equals the rate-limit interval (`period / calls`) for the active token type, so cache validity is bounded by the same window WB lets you refresh in. For Base tokens this turns 1/h endpoints into 1/h refreshes that subsequent CLI invocations can reuse without ever hitting the network.

Bypass for one invocation: `wb --no-cache <command>`. Bypass for a whole session: `WB_REQUEST_CACHE=disabled`. Diagnostics: `wb cache status` / `wb cache clear`. See [`RATE_LIMITS.md`](../../RATE_LIMITS.md#request-cache-i-15) for the full contract.