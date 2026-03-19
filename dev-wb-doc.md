Search

- General
- Introduction
  - How to get started with the API
  - Support
  - HTTP status codes
  - Rate Limits
- Authorization
  - Rules for using API access tokens
  - How to create a personal access, base, or test token
  - About the token
  - Token decode
- WB API Connection Check
  - getConnection Check{{ /ping }}
- News API
  - getGetting Seller Portal News{{ /api/communications/v2/news }}
- Seller Information
  - getGet Seller Information{{ /api/v1/seller-info }}
- Seller User Management
  - postCreate an Invitation for a New User{{ /api/v1/invite }}
  - getGet a List of Seller Active or Invited Users{{ /api/v1/users }}
  - putUpdate User's Access Permissions{{ /api/v1/users/access }}
  - delDelete User{{ /api/v1/user }}

[API docs by Redocly](https://redocly.com/redoc/)

# General(general)

In this section:

- [WB API general information](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction)
- how to [get started with the WB API](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/How-to-get-started-with-the-API)
- how to [log in](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization) and [create tokens](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token)
- main [HTTP status codes](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/HTTP-status-codes)
- [rate limits](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits)
- how to contact [support](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Support)

Use the methods in this section to:

- check the [WB API connection](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/WB-API-Connection-Check)
- get [seller portal news](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/News-API/paths/~1api~1communications~1v2~1news/get)
- get [seller information](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-Information)
- [manage seller users](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-User-Management)

## [tag/General](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/General) General

In this section:

- [WB API general information](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction)
- how to [get started with the WB API](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/How-to-get-started-with-the-API)
- how to [log in](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization) and [create tokens](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token)
- main [HTTP status codes](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/HTTP-status-codes)
- [rate limits](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits)
- how to contact [support](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Support)

Use the methods in this section to:

- check the [WB API connection](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/WB-API-Connection-Check)
- get [seller portal news](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/News-API/paths/~1api~1communications~1v2~1news/get)
- get [seller information](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-Information)
- [manage seller users](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-User-Management)

## [tag/Introduction](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Introduction) Introduction

The Wildberries API provides sellers with tools to manage their store and obtain real-time and statistical information via the HTTP REST API protocol.

The main advantage of the API is the ability to automate processes through integration with the seller's information systems, such as ERP, WMS, OMS, CRM. With the WB API, sellers can manage their store without manually using the website interface.

Using the API to operate a store on Wildberries is a great way to:

- automate routine processes
- access up-to-date information
- optimize inventory management

The API documentation is provided in the Swagger OpenAPI format and can be used for import into other tools, such as Postman, or for generating client code in various programming languages using Swagger CodeGen.

For manual API testing you can use:

- For Windows — [PostMan](https://www.postman.com/)
- For Linux — [curl](https://curl.se/)

## [tag/Introduction/How-to-get-started-with-the-API](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Introduction/How-to-get-started-with-the-API) How to get started with the API

1. Register in the [seller personal account](https://seller.wildberries.ru/).
2. Go to the store settings and [create an API token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token). The token will allow you to access the WB API. The token system lets you control who interacts with your data through the API and how.
3. Develop an integration with the API using your own developers or outsource specialists. You can also connect partner services from our [business solutions catalog](https://seller.wildberries.ru/auth-services).

Use the [connection test method](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/WB-API-Connection-Check) to find out if requests are successfully reaching the API and if the API token is configured correctly.

Practical tips:

- **Use the documentation**.

[Official WB API documentation](https://dev.wildberries.ru/en/docs/openapi/api-information) will help you understand the functionality and capabilities of the API. It includes examples of possible requests and responses, a list of potential errors, rate limits, security rules, and more.
- **Regularly check the integration**.

Ensure that you are transmitting data correctly and note the responses you receive to timely update the integration. Remember the restrictions and take into account the request limits.
- **Keep the API token secure**.

Do not share it with third parties unnecessarily. Use only trusted services. If you detect suspicious activity, immediately delete and replace the token.
- Contact [technical support](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Support) if needed.
- Stay updated on WB API news and changes in:
  - [release notes](https://dev.wildberries.ru/release-notes)
  - [Telegram channel](https://t.me/wb_api_notifications)
  - [Wildberries news feed](https://seller.wildberries.ru/news-v2/news-list)

## [tag/Introduction/Support](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Introduction/Support) Support

Technical support is conducted through dialogues in the [seller personal account](https://seller.wildberries.ru/). When creating a new support request, use the **API** category.

## [tag/Introduction/HTTP-status-codes](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Introduction/HTTP-status-codes) HTTP status codes

Main response status codes for requests in the WB API:

| Code | Description | How to resolve |
| --- | --- | --- |
| **200** | Success |  |
| **204** | Deleted/Updated/Confirmed |  |
| **400** | Bad request | Check the request syntax |
| **401** | Unauthorized | Check the authorization token. The token category must match the API category. Additionally, the token may be:<br>• expired<br>• incorrect<br>• missing from the request |
| **402** | Payment required | The error means that the service from the [Catalog](https://dev.wildberries.ru/business-solutions) has insufficient funds on its balance |
| **403** | Access denied | The token must not be generated by a deleted user. Access to the method must not be blocked. If you want to use the [Jam](https://seller.wildberries.ru/monetization/jam) methods, check your subscription in your personal account |
| **404** | Not found | Check the request URL |
| **409** | Status update error/Error adding label/etc | Check the request data. It must meet the service's requirements and limitations |
| **413** | The request body size exceeds the given limit | Reduce the number of objects in the request |
| **422** | Error processing request parameters/Unexpected result/etc | Check the request data. The request data must not contradict each other |
| **429** | Too many requests | Check the method rate limits and retry the request later |
| **5ХХ** | Internal service error | Service is unavailable. Retry the request later or contact WB technical support |

Pay attention to the `details` field in `404` and `429` errors — we add useful information there regarding the use of methods

Example of an error:

```json
{
  "title": "path not found",
  "detail": "Please consult the https://dev.wildberries.ru/openapi/api-information",
  ...
  "status": 404,
  "statusText": "Not Found",
  "timestamp": "2025-04-24T07:25:28Z"
}
```

## [tag/Introduction/Rate-Limits](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Introduction/Rate-Limits) Rate Limits

The WB API has request rate limits. To evenly distribute the load, the `token bucket` algorithm is used. Limits for specific API methods are specified in the documentation.

For example:

[Request limit](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits) per one seller account for all methods in the **Marketplace** category:

| Period | Limit | Interval | Burst |
| --- | --- | --- | --- |
| 1 minute | 300 requests | 200 milliseconds | 20 requests |

One request with a response code of `409` is counted as 5 requests

- **Period** — the time interval during which the maximum number of requests according to the limit can be sent.
- **Limit** — the maximum number of requests per period. In the example, up to 300 requests can be sent in one minute. Requests should be evenly distributed over time.
- **Interval** — the time gap for pauses between requests. In the example, it should be `60 seconds/300 requests` — `200 milliseconds` or `0.2 seconds`. Use the interval to evenly distribute the sending of requests.
- **Burst** — the maximum number of requests that can be sent simultaneously, without interval pauses. The allowed burst is also returned in the response header `X-Ratelimit-Remaining`. It appears in all response statuses except for error `429`.

`X-Ratelimit-Remaining` is the number of requests that can currently be sent without pauses. The value of `X-Ratelimit-Remaining` decreases by one after each request. If `X-Ratelimit-Remaining` is `0` and you make the next request without a delay, you will receive a `429` error in response. The value of `X-Ratelimit-Remaining` is restored over time.

There are cases where one request can count as multiple requests. For example, if you send requests in the [Marketplace](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token) category, a request with a `409` error will count as 10 requests with other statuses. In such cases, the value of `X-Ratelimit-Remaining` will decrease by 10 units immediately.

If you exceed the request rate limit, you will receive a `429` error. In this case, you need to wait a short period before making the next request. To determine how long you need to wait, use the headers from the `429` response:

- `X-Ratelimit-Retry` — the number of seconds after which you can retry the request. If you attempt it earlier, you will continue to receive a `429` error.
- `X-Ratelimit-Limit` — the maximum allowable burst of requests, which will be replenished after `X-Ratelimit-Reset` seconds.
- `X-Ratelimit-Reset` — the number of seconds after which the allowable burst of requests will be restored to the maximum value specified in `X-Ratelimit-Limit`.

Response example:

```sh
HTTP/1.1 429 Too Many Requests
...
X-Ratelimit-Reset: 29
X-Ratelimit-Retry: 2
...
X-Ratelimit-Limit: 10
```

## [tag/Authorization](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization) Authorization

You need API token to authenticate requests. It is valid for 180 days after creation. Add the token to the `Authorization` request header.

According to clause 9.9.6 of the offer, integration with the seller portal without [WB API](https://dev.wildberries.ru/en) is prohibited.

## [tag/Authorization/Rules-for-using-API-access-tokens](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization/Rules-for-using-API-access-tokens) Rules for using API access tokens

The procedure and grounds for revoking access tokens are set out in the [Agreement on the Placement of Authorized Services on the WB API Platform](https://legal.wildberries.ru/soglashenie-o-razmeschenii-avtorizovannykh-servisov-na-platforme-wb-api/country/ru/lang/ru/).

You can learn more about tokens from the [guide in the Help Center](https://seller.wildberries.ru/instructions/ru/ru/material/api-integration-with-token)

Four types of tokens are available for authorization:

Access to WB API methods depends on the selected token type

1. **Personal token**

- **Purpose:** An exclusive token with advanced features. It is designed to grant access to seller data only to your own programs, including corporate (on-premise) systems hosted on your own or third-party infrastructure.

Advanced features mean that over time, a personal access token will provide access to additional categories of seller data that are not available with the basic token. We will announce this in the news in advance.
- **Suitable for:**
  - a company's own software products or systems hosted on its own or third-party servers
  - ready-made on-premise ERP/CRM systems, including local (packaged) versions of 1C hosted on company servers or user computers
- **Restrictions:** A personal access token provides access to sensitive information, so it must not be shared with third parties or used in cloud services. When creating the token, the system will display a liability warning — you must accept it to proceed.

You choose the token settings yourself. If you are unsure which parameters to specify, check with the developer or IT specialist responsible for the system you are connecting.

2. **Service token**

- **Purpose:** A special token for connecting a specific cloud service from the official [Catalog of business solutions](https://dev.wildberries.ru/en/business-solutions) on **Wildberries**.
- **Features:** Select a service from the [Catalog](https://dev.wildberries.ru/en/business-solutions) when creating the token. Then all necessary settings, including data categories and access levels, are filled in automatically. You only need to confirm the token creation and provide it to the service.
- **Restrictions:** Token is created for one service only and doesn't work with any other

3. **Base token**

- **Purpose:** An additional token that provides access to a limited set of seller data and is used in all cases where a service or personal access token is not suitable.
- **Suitable for:**
  - testing integration on real data before launch
  - other cases where you cannot use a service or personal access token
- **Restrictions:** You can only work with a limited set of data.

4. **Test token**

- **Purpose:** A special token for securely testing and debugging integrations in an isolated environment — the [WB API sandbox](https://dev.wildberries.ru/en/sandbox).
- **Suitable for:**
  - developing and debugging integrations without risk to real data
  - exploring API capabilities and experimenting with methods
  - testing new features before launching in the production environment
- **Restrictions:** A test token only works with the sandbox and provides access to generated test data. Real seller data is not accessible.

## [tag/Authorization/How-to-create-a-personal-access-base-or-test-token](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization/How-to-create-a-personal-access-base-or-test-token) How to create a personal access, base, or test token

You can learn more about creating a **Service token** from the [guide in the Help Center](https://seller.wildberries.ru/instructions/ru/ru/material/how-to-create-update-or-delete-a-wb-api-token?categoryId=api-integration&goBackOption=prevRoute#%D0%BA%D0%B0%D0%BA-%D1%81%D0%BE%D0%B7%D0%B4%D0%B0%D1%82%D1%8C-%D1%81%D0%B5%D1%80%D0%B2%D0%B8%D1%81%D0%BD%D1%8B%D0%B9-%D1%82%D0%BE%D0%BA%D0%B5%D0%BD)

1. In your personal access account, go to the [API Integrations](https://seller.wildberries.ru/api-integrations) section.
2. Click **\+ Create token**. A window for creating token with two tabs will open. For all token types except Service token, select the **Manual integration** tab.
3. Choose the token type.
4. For base and personal access tokens:

- Enter the token name
- Select the API categories you will be working with
- Set the data access level: **Read and Write** or **Read Only**

| Category | Methods |
| --- | --- |
| Content | [Categories, Subjects and Characteristics](https://dev.wildberries.ru/en/docs/openapi/work-with-products#tag/Categories-Subjects-and-Characteristics)<br>[Creating Product Cards](https://dev.wildberries.ru/en/docs/openapi/work-with-products#tag/Creating-Product-Cards)<br>[Product Cards](https://dev.wildberries.ru/en/docs/openapi/work-with-products#tag/Product-Cards)<br>[Media-Files](https://dev.wildberries.ru/en/docs/openapi/work-with-products#tag/Media-Files)<br>[Tags](https://dev.wildberries.ru/en/docs/openapi/work-with-products#tag/Tags) |
| Analytics | [Sales Funnel](https://dev.wildberries.ru/en/docs/openapi/analytics#tag/Sales-Funnel)<br>[Search Queries for Your Items](https://dev.wildberries.ru/en/docs/openapi/analytics#tag/Search-Queries-for-Your-Items)<br>[Stocks Report](https://dev.wildberries.ru/en/docs/openapi/analytics#tag/Stocks-Report)<br>[Seller Analytics CSV](https://dev.wildberries.ru/en/docs/openapi/analytics#tag/Seller-Analytics-CSV)<br>[Warehouses Remains Report](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Warehouses-Remains-Report)<br>[Report on Products with Mandatory Labeling](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Report-on-Products-with-Mandatory-Labeling)<br>[Retention Reports](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Retention-Reports)<br>[Paid Reception](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Paid-Reception)<br>[Paid Storage](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Paid-Storage)<br>[Sales by Regions](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Sales-by-Regions)<br>[Share of Brand in Sales](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Share-of-Brand-in-Sales)<br>[Hidden Products](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Hidden-Products)<br>[Goods Return Report](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Goods-Return-Report) |
| Prices and Discounts | [Prices and Discounts](https://dev.wildberries.ru/en/docs/openapi/work-with-products#tag/Prices-and-Discounts)<br>[Promotions Calendar](https://dev.wildberries.ru/en/docs/openapi/promotion#tag/Promotions-Calendar) |
| Marketplace | [FBS Orders](https://dev.wildberries.ru/en/docs/openapi/orders-fbs)<br>[Seller Warehouses](https://dev.wildberries.ru/en/docs/openapi/work-with-products#tag/Seller-Warehouses)<br>[Inventory](https://dev.wildberries.ru/en/docs/openapi/work-with-products#tag/Inventory)<br>[DBS Orders](https://dev.wildberries.ru/en/docs/openapi/orders-dbs)<br>[In-Store Pickup](https://dev.wildberries.ru/en/docs/openapi/in-store-pickup) |
| Statistics | [Main Reports](https://dev.wildberries.ru/en/docs/openapi/reports#tag/Main-Reports)<br>[Financial Reports](https://dev.wildberries.ru/en/docs/openapi/financial-reports-and-accounting#tag/Financial-Reports) |
| Promotion | [Campaigns](https://dev.wildberries.ru/en/docs/openapi/promotion#tag/Campaigns)<br>[Campaigns Creation](https://dev.wildberries.ru/en/docs/openapi/promotion#tag/Campaigns-Creation)<br>[Campaigns Management](https://dev.wildberries.ru/en/docs/openapi/promotion#tag/Campaigns-Management)<br>[Campaign Parameters](https://dev.wildberries.ru/en/docs/openapi/promotion#tag/Campaign-Parameters)<br>[Finance](https://dev.wildberries.ru/en/docs/openapi/promotion#tag/Finance)<br>[Media](https://dev.wildberries.ru/en/docs/openapi/promotion#tag/Media)<br>[Statistics](https://dev.wildberries.ru/en/docs/openapi/promotion#tag/Statistics) |
| Feedbacks and Questions | [Questions](https://dev.wildberries.ru/en/docs/openapi/user-communication#tag/Questions)<br>[Feedbacks](https://dev.wildberries.ru/en/docs/openapi/user-communication#tag/Feedbacks)<br>[Pinned Feedback](https://dev.wildberries.ru/en/docs/openapi/user-communication#tag/Pinned-Feedback) |
| Buyers Chat | [Buyers Chat](https://dev.wildberries.ru/en/docs/openapi/user-communication#tag/Buyers-Chat) |
| Supplies | [FBW Supplies](https://dev.wildberries.ru/en/docs/openapi/orders-fbw#tag/FBW-Supplies) |
| Buyers Returns | [Buyers Returns](https://dev.wildberries.ru/en/docs/openapi/user-communication#tag/Buyers-Returns) |
| Documents | [Documents](https://dev.wildberries.ru/en/docs/openapi/financial-reports-and-accounting#tag/Documents) |
| Finance | [Balance](https://dev.wildberries.ru/en/docs/openapi/financial-reports-and-accounting#tag/Balance) |
| Users | [Seller User Management](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-User-Management) |

Only select the categories you plan to work with. For example, if you will only upload product cards, select only Content category. If someone gets your token, they will not be able to gain access to the other API categories of your store.

5. Optionally, add a comment to the token. For a personal access token, check the **I understand that the token should not be shared with third parties** box.
6. Click **Create**. A window with your token will appear.
7. Click the **Copy and close** button — the window will close, and the token will be copied to the clipboard. After this, you will not be able to view the token in your personal account again.
8. Save the token in a safe place. If you lose the token, create a new one.

If you have several services (integrations) that work with different categories, create a token for each service. This will allow access to only the necessary categories, as well as more flexible and secure management of integrations.

## [tag/Authorization/About-the-token](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization/About-the-token) About the token

The token is a JWT according to [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519). To check if your token is valid and which categories of API methods are available with it, you can [decode it](https://dev.wildberries.ru/en/jwt?utm_source=dev-portal&utm_campaign=api-information&utm_content=cta-link).

We recommend not to view the token using online tools so no one can take it over.

**Token fields**

The token type can be determined by the list of fields from the decoded token `payload`:

| Token | `acc` value | `for` value | `t` value |
| --- | --- | --- | --- |
| Base token | `1` | The field is missing | `false` |
| Test token | `2` | The field is missing | `true` |
| Personal access token | `3` | `self` | `false` |
| Service token | `4` | `asid:{Service ID}` | `false` |

Other fields:

| **Field** | **Type** | **Description** |
| --- | --- | --- |
| **id** | UUIDv4 | Unique token ID |
| **s** | uint | Token properties bitmask |
| **sid** | UUIDv4 | Wildberries seller ID |
| **exp** | uint | Token lifetime, complies with [RFC 7519: JSON Web Token (JWT)](https://www.rfc-editor.org/rfc/rfc7519#section-4.1.4) |

The remaining `payload` fields are for internal use and may be removed.

**`s` field**

The `s` field is a bitmask, an integer, each bit of which means the presence or absence of some option.

[Learn more about bitmask](https://en.wikipedia.org/wiki/Mask_(computing))

**Bit values**

| **Bit position** | **Property (if bit is 1)** |
| --- | --- |
| 1 | Access to **Content** |
| 2 | Access to **Analytics** |
| 3 | Access to **Prices and discounts** |
| 4 | Access to **Marketplace** |
| 5 | Access to **Statistics** |
| 6 | Access to **Promotion** |
| 7 | Access to **Feedbacks and Questions** |
| 9 | Access to **Buyers chat** |
| 10 | Access to **Supplies** |
| 11 | Access to **Buyers returns** |
| 12 | Access to **Documents** |
| 13 | Access to **Finance** |
| 16 | Access to **Users** |
| 30 | Read only token |

## [tag/Authorization/Token-decode](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization/Token-decode) Token decode

Token decoding will allow to check if the token is valid and which categories of API methods are available. You can decode the token on the [separate page](https://dev.wildberries.ru/en/jwt?utm_source=dev-portal&utm_campaign=api-information&utm_content=cta-link).

## [tag/WB-API-Connection-Check](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/WB-API-Connection-Check) WB API Connection Check

You can check connection with a [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token) of any category

## [tag/WB-API-Connection-Check/paths/~1ping/get](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/WB-API-Connection-Check/paths/~1ping/get) Connection Check{{ /ping }}

get/ping

https://common-api.wildberries.ru/ping

Описание метода

Checks:

1. Whether the request successfully reaches the WB API.
2. The validity of the authorization token and request URL.
3. Whether the token category matches the service.

This method is not intended to check the availability of WB services

Each service has its own version of the method depending on the domain:

| Category | Request URL |
| --- | --- |
| Content | `https://content-api.wildberries.ru/ping`<br>`https://content-api-sandbox.wildberries.ru/ping` |
| Analytics | `https://seller-analytics-api.wildberries.ru/ping` |
| Prices and Discounts | `https://discounts-prices-api.wildberries.ru/ping`<br>`https://discounts-prices-api-sandbox.wildberries.ru/ping` |
| Marketplace | `https://marketplace-api.wildberries.ru/ping` |
| Statistics | `https://statistics-api.wildberries.ru/ping`<br>`https://statistics-api-sandbox.wildberries.ru/ping` |
| Promotion | `https://advert-api.wildberries.ru/ping`<br>`https://advert-api-sandbox.wildberries.ru/ping` |
| Feedbacks and Questions | `https://feedbacks-api.wildberries.ru/ping`<br>`https://feedbacks-api-sandbox.wildberries.ru/ping` |
| Buyers Chat | `https://buyer-chat-api.wildberries.ru/ping` |
| Supplies | `https://supplies-api.wildberries.ru/ping` |
| Buyers Returns | `https://returns-api.wildberries.ru/ping` |
| Documents | `https://documents-api.wildberries.ru/ping` |
| Finance | `https://finance-api.wildberries.ru/ping` |
| Tariffs, News, Seller Information | `https://common-api.wildberries.ru/ping` |
| Seller User Management | `https://user-management-api.wildberries.ru/ping` |

A maximum of 3 requests every 30 [seconds](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits). If you try to use this method programmatically, the method will be temporarily blocked. The rate limit applies individually to each instance of the method on each host

##### Authorizations:

_HeaderApiKey_

### Responses

**200**

Success

**401**

Unauthorized

**429**

Too many requests

### Response samples

- 200
- 401
- 429

Content type

application/json

Copy

`{"TS": "2024-08-16T11:19:05+03:00",

"Status": "OK"

}`

## [tag/News-API](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/News-API) News API

You can get Seller Portal News with a [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token) of any category

## [tag/News-API/paths/~1api~1communications~1v2~1news/get](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/News-API/paths/~1api~1communications~1v2~1news/get) Getting Seller Portal News{{ /api/communications/v2/news }}

get/api/communications/v2/news

https://common-api.wildberries.ru/api/communications/v2/news

Описание метода

The method allows getting news from the seller portal.

To receive a successful response, one of the parameters `from` or `fromID` must be specified.

You can get up to 100 news items per request.

[Request limit](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits) per one seller's account:

| Period | Limit | Interval | Burst |
| --- | --- | --- | --- |
| 1 min | 1 request | 1 min | 10 requests |

##### Authorizations:

_HeaderApiKey_

##### query Parameters

|     |     |
| --- | --- |
| from | string<date><br>Example:from=2025-02-06<br>Date from which to get news |
| fromID | integer<uint64><br>Example:fromID=7369<br>The news ID, starting from which — including it — you need to get the list of news |

### Responses

**200**

Success

**400**

Bad request

**401**

Unauthorized

**429**

Too many requests

### Response samples

- 200
- 401
- 429

Content type

application/json

Copy
Expand all  Collapse all

`{"data": [{"content": "Теперь в кампаниях ВБ.Медиа вы можете размещать баннеры для пользователей, которые взаимодействовали\nс товарами из определённой категории: покупали, искали, добавляли в корзину и избранное. Также можно\nвыбрать период, за который хотите учитывать эти действия.Например, вы продаёте обувь. Рекламу можно\nпоказать людям, которые добавляли в корзину или избранное товары из этой категории за последние 14\nдней. Возможно, пользователи, которые попадают под этот критерий, уже совершили покупку. Поэтому вы\nможете уточнить настройки показа: добавить параметр «Не покупал товар из категории „Обувь“ в последние\n14 дней». Так вероятность того, что ваш баннер приведёт к покупке, будет выше.Чтобы запустить рекламу,\nсоздайте в кабинете ВБ.Медиа кампанию «По показам» и на шаге 4 включите «Поведенческие параметры».\nЭти параметры можно комбинировать с таргетированием по предполагаемым интересам, полу, возрасту и\nрегиону.Подробнее о том, как настроить таргетинг, — в инструкции «По показам».Запустить рекламу на\nWildberries\n",\
\
"date": "2025-02-05T14:10:35+03:00",\
\
"header": "Новые настройки кампаний в ВБ.Медиа: таргетируйте рекламу в зависимости от того, как аудитория\nиспользует сервисы Wildberries\n",\
\
"id": 7369,\
\
"types": [{"id": 4,\
\
"name": "Маркетинг"\
\
}\
\
]\
\
},\
\
{"content": "Добавили получение отчётов по текстам поисковых запросов в формате CSV. В описания методов «Создать\nотчёт» и «Получить отчёт» добавили описания и примеры моделей: • запросов — SearchReportTextReq, •\nуспешных ответов (статус-код 200) — SearchReportTextRes.В ответ метода «Поисковые запросы по товару»\nдобавили 8 полей и структуры price и medianPosition. Узнать больше можно в Журнале изменений.Эти методы\nдоступны только с подпиской «Джем»\n",\
\
"date": "2025-02-06T18:14:58+03:00",\
\
"header": "Изменения в API «Аналитики и данных»",\
\
"id": 7373,\
\
"types": [{"id": 8,\
\
"name": "API"\
\
},\
\
{"id": 41,\
\
"name": "Аналитика продавца"\
\
}\
\
]\
\
}\
\
]

}`

## [tag/Seller-Information](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Seller-Information) Seller Information

Seller information can be obtained with a [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token) of any category.

## [tag/Seller-Information/paths/~1api~1v1~1seller-info/get](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Seller-Information/paths/~1api~1v1~1seller-info/get) Get Seller Information{{ /api/v1/seller-info }}

get/api/v1/seller-info

https://common-api.wildberries.ru/api/v1/seller-info

Описание метода

This method allows you to obtain the seller's name and account ID.

You can use any token in request, as long as the **Test Environment** option is not selected.

[Request limit](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits) per one seller's account:

| Period | Limit | Interval | Burst |
| --- | --- | --- | --- |
| 1 min | 1 request | 1 min | 10 requests |

##### Authorizations:

_HeaderApiKey_

### Responses

**200**

Success

**401**

Unauthorized

**402**

Payment required

**429**

Too many requests

### Response samples

- 200
- 401
- 402
- 429

Content type

application/json

Copy

`{"name": "ИП Кружинин В. Р.",

"sid": "e8923014-e233-47q8-898e-3cc86d67ea61",

"tradeMark": "Flax Store"

}`

## [tag/Seller-User-Management](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Seller-User-Management) Seller User Management

To access the methods, use a [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token) for the **Users** category

With these methods, you can:

- [Create an invitation for a user](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-User-Management/paths/~1api~1v1~1invite/post) with access to the seller account
- [Get a list of the seller active or invited users](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-User-Management/paths/~1api~1v1~1users/get)
- [Update user's access permissions](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-User-Management/paths/~1api~1v1~1users~1access/put) for the seller account
- [Revoke a user's access](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-User-Management/paths/~1api~1v1~1user/delete) to the seller account

You can manage user access only with a token from the active owner of the seller account.

## [tag/Seller-User-Management/paths/~1api~1v1~1invite/post](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Seller-User-Management/paths/~1api~1v1~1invite/post) Create an Invitation for a New User{{ /api/v1/invite }}

post/api/v1/invite

https://user-management-api.wildberries.ru/api/v1/invite

Описание метода

Method is available by **Personal** [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/Rules-for-using-API-access-tokens)

The method creates an invitation for a new user with access settings to the seller account sections.

How access rights are assigned:

- If `access` is empty (`[]`) or not provided — by default, all access is granted, except for access to the showcase (`showcase`) and **Jam** (`changeJam`)
- If `access` specifies some of the account sections, then in addition to the access rights specified in the request, all default access rights are also granted
- If `access` lists all possible sections, access rights will be granted according to the request, without the default access rights
- If the same section (`code`) is specified twice in `access`:
  - with different `disabled` values (`true` and `false`), access will not be granted
  - with identical values of `"disabled": true`, access will not be granted
  - with identical values of `"disabled": false`, access will be granted

[Request limit](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits) per one seller's account:

| Period | Limit | Interval | Burst |
| --- | --- | --- | --- |
| 1 s | 1 request | 1 s | 5 requests |

##### Authorizations:

_HeaderApiKey_

##### Request Body schema: application/json  required

|     |     |
| --- | --- |
| access | Array of objects (Access) <br>Access settings for seller account sections |
| invite<br>required | object |

### Responses

**200**

Success

**400**

Bad request

**401**

Unauthorized

**429**

Too many requests

### Request samples

- Payload

Content type

application/json

Copy
Expand all  Collapse all

`{"access": [{"code": "balance",\
\
"disabled": false\
\
},\
\
{"code": "pointsForReviews",\
\
"disabled": false\
\
},\
\
{"code": "brands",\
\
"disabled": true\
\
},\
\
{"code": "finance",\
\
"disabled": true\
\
},\
\
{"code": "supply",\
\
"disabled": true\
\
}\
\
],

"invite": {"phoneNumber": "79999999999",

"position": "Менеджер"

}

}`

### Response samples

- 200
- 400
- 401
- 429

Content type

application/json

Copy

`{"inviteID": "741b8aa6-08ac-4782-8a9d-d931bcbbf608",

"expiredAt": "2025-10-06T10:56:04.335060746Z",

"isSuccess": true,

"inviteUrl": "https://seller.wildberries.ru/supplier-settings/supplier-card?inviteId=e5a813c7-65e0-4599-a550-a6b3d85661ed"

}`

## [tag/Seller-User-Management/paths/~1api~1v1~1users/get](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Seller-User-Management/paths/~1api~1v1~1users/get) Get a List of Seller Active or Invited Users{{ /api/v1/users }}

get/api/v1/users

https://user-management-api.wildberries.ru/api/v1/users

Описание метода

Method is available by **Personal** [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/Rules-for-using-API-access-tokens)

The method returns a list of seller account active or invited users.

Specify the value of the `isInviteOnly` parameter to select the list:

- `isInviteOnly=true` — invited users list who have not yet activated access
- `isInviteOnly=false` or is not provided — active users list

For each user, you can get:

- user's role
- accessible sections
- invitation status

The list of invited users in the response is always sorted by creation date: from newest to oldest.

[Request limit](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits) per one seller's account:

| Period | Limit | Interval | Burst |
| --- | --- | --- | --- |
| 1 s | 1 request | 1 s | 5 requests |

##### Authorizations:

_HeaderApiKey_

##### query Parameters

|     |     |
| --- | --- |
| limit | integer<int64><= 100<br>Default:100<br>The number of active or invited users in the response |
| offset | integer<int64><br>Default:0<br>How many results to skip. For example, for the value 10, the response will start with the 11 element |
| isInviteOnly | boolean<br>Default:false<br>- `true` — the list of invited users who have not yet activated access<br>- `false` or not provided — the list of active users of the seller account |

### Responses

**200**

Success

**400**

Bad request

**401**

Unauthorized

**429**

Too many requests

### Response samples

- 200
- 400
- 401
- 429

Content type

application/json

Example

isInviteOnly=trueisInviteOnly=falseisInviteOnly=true

List of invited users

Copy
Expand all  Collapse all

`{"total": 2,

"countInResponse": 2,

"users": [{"id": 0,\
\
"role": "",\
\
"position": "Аналитик",\
\
"phone": "79998888888",\
\
"email": "",\
\
"isOwner": false,\
\
"firstName": "",\
\
"secondName": "",\
\
"patronymic": "",\
\
"goodsReturn": false,\
\
"isInvitee": true,\
\
"inviteeInfo": {"phoneNumber": "79998888888",\
\
"position": "Аналитик",\
\
"inviteUuid": "00000000-0000-4000-8000-000000000001",\
\
"expiredAt": "2025-12-01T00:00:00Z",\
\
"isActive": true\
\
},\
\
"access": [{"code": "supply",\
\
"disabled": true\
\
},\
\
{"code": "changeJam",\
\
"disabled": true\
\
},\
\
{"code": "showcase",\
\
"disabled": false\
\
},\
\
{"code": "suppliersDocuments",\
\
"disabled": false\
\
},\
\
{"code": "discountPrice",\
\
"disabled": true\
\
},\
\
{"code": "feedbacks",\
\
"disabled": false\
\
},\
\
{"code": "questions",\
\
"disabled": false\
\
},\
\
{"code": "wbPoint",\
\
"disabled": false\
\
},\
\
{"code": "brands",\
\
"disabled": true\
\
},\
\
{"code": "pointsForReviews",\
\
"disabled": false\
\
},\
\
{"code": "pinFeedbacks",\
\
"disabled": false\
\
},\
\
{"code": "finance",\
\
"disabled": true\
\
},\
\
{"code": "feedbacksQuestions",\
\
"disabled": false\
\
},\
\
{"code": "balance",\
\
"disabled": false\
\
}\
\
]\
\
},\
\
{"id": 0,\
\
"role": "",\
\
"position": "",\
\
"phone": "7999XXXX102",\
\
"email": "",\
\
"isOwner": false,\
\
"firstName": "",\
\
"secondName": "",\
\
"patronymic": "",\
\
"goodsReturn": false,\
\
"isInvitee": true,\
\
"inviteeInfo": {"phoneNumber": "79996666666",\
\
"position": "Аналитик",\
\
"inviteUuid": "00000000-0000-4000-8000-000000000002",\
\
"expiredAt": "2025-12-10T00:00:00Z",\
\
"isActive": false\
\
},\
\
"access": [{"code": "supply",\
\
"disabled": true\
\
},\
\
{"code": "changeJam",\
\
"disabled": true\
\
},\
\
{"code": "showcase",\
\
"disabled": false\
\
},\
\
{"code": "suppliersDocuments",\
\
"disabled": false\
\
},\
\
{"code": "discountPrice",\
\
"disabled": true\
\
},\
\
{"code": "feedbacks",\
\
"disabled": false\
\
},\
\
{"code": "questions",\
\
"disabled": false\
\
},\
\
{"code": "wbPoint",\
\
"disabled": false\
\
},\
\
{"code": "brands",\
\
"disabled": true\
\
},\
\
{"code": "pointsForReviews",\
\
"disabled": false\
\
},\
\
{"code": "pinFeedbacks",\
\
"disabled": false\
\
},\
\
{"code": "finance",\
\
"disabled": true\
\
},\
\
{"code": "feedbacksQuestions",\
\
"disabled": false\
\
},\
\
{"code": "balance",\
\
"disabled": false\
\
}\
\
]\
\
}\
\
]

}`

## [tag/Seller-User-Management/paths/~1api~1v1~1users~1access/put](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Seller-User-Management/paths/~1api~1v1~1users~1access/put) Update User's Access Permissions{{ /api/v1/users/access }}

put/api/v1/users/access

https://user-management-api.wildberries.ru/api/v1/users/access

Описание метода

Method is available by **Personal** [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/Rules-for-using-API-access-tokens)

The method changes the access rights for one or more users.

Only the data passed in the request parameters will be updated. The other fields will remain unchanged.

[Request limit](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits) per one seller's account:

| Period | Limit | Interval | Burst |
| --- | --- | --- | --- |
| 1 s | 1 request | 1 s | 5 requests |

##### Authorizations:

_HeaderApiKey_

##### Request Body schema: application/json  required

|     |     |
| --- | --- |
| usersAccesses<br>required | Array of objects (UserAccess) <br>Access settings for user |

### Responses

**200**

Success

**400**

Bad request

**401**

Unauthorized

**429**

Too many requests

### Request samples

- Payload

Content type

application/json

Copy
Expand all  Collapse all

`{"usersAccesses": [{"userId": 42334965,\
\
"access": [{"code": "balance",\
\
"disabled": false\
\
},\
\
{"code": "finance",\
\
"disabled": true\
\
},\
\
{"code": "feedbacks",\
\
"disabled": false\
\
}\
\
]\
\
},\
\
{"userId": 52334965,\
\
"access": [{"code": "balance",\
\
"disabled": true\
\
},\
\
{"code": "changeJam",\
\
"disabled": false\
\
},\
\
{"code": "showcase",\
\
"disabled": false\
\
}\
\
]\
\
}\
\
]

}`

### Response samples

- 400
- 401
- 429

Content type

application/json

Copy

`{"title": "Bad Request",

"status": 400,

"detail": "bad request cause: user is not in current supplier",

"requestId": "c479c04d0b576a9ba0b20fdf235004c2",

"origin": "public-acl"

}`

## [tag/Seller-User-Management/paths/~1api~1v1~1user/delete](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Seller-User-Management/paths/~1api~1v1~1user/delete) Delete User{{ /api/v1/user }}

delete/api/v1/user

https://user-management-api.wildberries.ru/api/v1/user

Описание метода

Method is available by **Personal** [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/Rules-for-using-API-access-tokens)

The method removes a user from [the seller user list](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Seller-User-Management/paths/~1api~1v1~1users/get). This user will no longer have access to the seller account.

[Request limit](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits) per one seller's account:

| Period | Limit | Interval | Burst |
| --- | --- | --- | --- |
| 1 s | 1 request | 1 s | 10 requests |

##### Authorizations:

_HeaderApiKey_

##### query Parameters

|     |     |
| --- | --- |
| deletedUserID<br>required | integer<int64><br>ID of the user whose access will be revoked |

### Responses

**200**

Success

**400**

Bad request

**401**

Unauthorized

**429**

Too many requests

### Response samples

- 400
- 401
- 429

Content type

application/json

Copy

`{"title": "Bad Request",

"status": 400,

"detail": "bad request cause: user is not in current supplier",

"requestId": "c479c04d0b576a9ba0b20fdf235004c2",

"origin": "public-acl"

}`