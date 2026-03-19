## [Authorization](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization)

You need API token to authenticate requests. It is valid for 180 days after creation. Add the token to the `Authorization` request header.

> According to clause 9.9.6 of the offer, integration with the seller portal without [WB API](https://dev.wildberries.ru/en) is prohibited.

## [Rules for using API access tokens](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization/Rules-for-using-API-access-tokens) 

> The procedure and grounds for revoking access tokens are set out in the [Agreement on the Placement of Authorized Services on the WB API Platform](https://legal.wildberries.ru/soglashenie-o-razmeschenii-avtorizovannykh-servisov-na-platforme-wb-api/country/ru/lang/ru/).

> You can learn more about tokens from the [guide in the Help Center](https://seller.wildberries.ru/instructions/ru/ru/material/api-integration-with-token)

Four types of tokens are available for authorization:

> Access to WB API methods depends on the selected token type

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

## [How to create a personal access, base, or test token](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization/How-to-create-a-personal-access-base-or-test-token) 

> You can learn more about creating a **Service token** from the [guide in the Help Center](https://seller.wildberries.ru/instructions/ru/ru/material/how-to-create-update-or-delete-a-wb-api-token?categoryId=api-integration&goBackOption=prevRoute#%D0%BA%D0%B0%D0%BA-%D1%81%D0%BE%D0%B7%D0%B4%D0%B0%D1%82%D1%8C-%D1%81%D0%B5%D1%80%D0%B2%D0%B8%D1%81%D0%BD%D1%8B%D0%B9-%D1%82%D0%BE%D0%BA%D0%B5%D0%BD)

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

> Only select the categories you plan to work with. For example, if you will only upload product cards, select only Content category. If someone gets your token, they will not be able to gain access to the other API categories of your store.

5. Optionally, add a comment to the token. For a personal access token, check the **I understand that the token should not be shared with third parties** box.
6. Click **Create**. A window with your token will appear.
7. Click the **Copy and close** button — the window will close, and the token will be copied to the clipboard. After this, you will not be able to view the token in your personal account again.
8. Save the token in a safe place. If you lose the token, create a new one.

> If you have several services (integrations) that work with different categories, create a token for each service. This will allow access to only the necessary categories, as well as more flexible and secure management of integrations.

## [About the token](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization/About-the-token) 

The token is a JWT according to [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519). To check if your token is valid and which categories of API methods are available with it, you can [decode it](https://dev.wildberries.ru/en/jwt?utm_source=dev-portal&utm_campaign=api-information&utm_content=cta-link).

> We recommend not to view the token using online tools so no one can take it over.

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

## [Token decode](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/Authorization/Token-decode) 

Token decoding will allow to check if the token is valid and which categories of API methods are available. You can decode the token on the [separate page](https://dev.wildberries.ru/en/jwt?utm_source=dev-portal&utm_campaign=api-information&utm_content=cta-link).

## [WB API Connection Check](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/WB-API-Connection-Check) 

> You can check connection with a [token](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization/How-to-create-a-personal-access-base-or-test-token) of any category

## [Connection Check `/ping`](https://dev.wildberries.ru/en/docs/openapi/api-information\#tag/WB-API-Connection-Check/paths/~1ping/get)


[GET] `https://common-api.wildberries.ru/ping`

Content type: application/json

Responses: 200, 401, 439

```json
{
  "TS": "2024-08-16T11:19:05+03:00",
  "Status": "OK"
}
```

Method description

Checks:

1. Whether the request successfully reaches the WB API.
2. The validity of the authorization token and request URL.
3. Whether the token category matches the service.

> This method is not intended to check the availability of WB services

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

> A maximum of 3 requests every 30 [seconds](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Introduction/Rate-Limits). If you try to use this method programmatically, the method will be temporarily blocked. The rate limit applies individually to each instance of the method on each host

##### Authorizations:

Header parameter name: `Authorization`

### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **401** | Unauthorized |
| **429** | Too many requests |

### Response samples

#### 200
- Response Schema: application/json
- Content type: application/json

| Param | Type | Description |
| TS	| string	| Request timestamp	|
| Status	| string	| Value: "OK"	|


#### 401
- Response Schema: application/problem+json
- Content type: application/json

| Param | Type | Description |
| title |string | Error title |
| detail |string | Error details |
| code |string | Internal error code |
| requestId |string | Unique request ID |
| origin |string | WB internal service ID |
| status |number | HTTP status code |
| statusText |string | Text of the HTTP status code |
| timestamp |string <date-time> | Request date and time |

#### 429
- Response Schema: application/problem+json
- Content type: application/json

| Param | Type | Description |
| title |string | Error title |
| detail |string | Error details |
| code |string | Internal error code |
| requestId |string | Unique request ID |
| origin |string | WB internal service ID |
| status |number | HTTP status code |
| statusText |string | Text of the HTTP status code |
| timestamp |string <date-time> | Request date and time |
