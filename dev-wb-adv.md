# Marketing and Promotions

> Campaign Management, bid settings, financial data accounting, and settings for with standard and custom bid and media campaigns.
> Data synchronization from the database occurs every 3 minutes. Status changes occur every 1 minute. The bid change occurs every 30 seconds. The latest changes are saved within the intervals

## Endpoint Index

### advert-api.wildberries.ru (Promotion token)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/adv/v1/promotion/count` | Campaigns lists grouped by type and status |
| GET | `/api/advert/v2/adverts` | Campaigns information (bids, settings, statuses) |
| POST | `/api/advert/v1/bids/min` | Minimum bids for product cards |
| POST | `/adv/v2/seacat/save-ad` | Create campaign |
| GET | `/adv/v1/supplier/subjects` | Subjects for campaigns |
| POST | `/adv/v2/supplier/nms` | Product cards for campaigns |
| GET | `/adv/v0/delete` | Delete campaign |
| POST | `/adv/v0/rename` | Rename campaign |
| GET | `/adv/v0/start` | Launch campaign |
| GET | `/adv/v0/pause` | Pause campaign |
| GET | `/adv/v0/stop` | Stop campaign |
| PUT | `/adv/v0/auction/placements` | Change placements (custom bid) |
| PATCH | `/api/advert/v1/bids` | Change campaign bids |
| PATCH | `/adv/v0/auction/nms` | Change product cards in campaigns |
| GET | `/api/advert/v0/bids/recommendations` | Recommended bids for items and clusters |
| POST | `/adv/v0/normquery/get-bids` | List search clusters bids |
| POST | `/adv/v0/normquery/bids` | Set bids for search clusters |
| DELETE | `/adv/v0/normquery/bids` | Delete bids from search clusters |
| POST | `/adv/v0/normquery/get-minus` | List minus phrases |
| POST | `/adv/v0/normquery/set-minus` | Set/delete minus phrases |
| POST | `/adv/v0/normquery/list` | Active/inactive search cluster lists |
| GET | `/adv/v1/balance` | Seller balance |
| GET | `/adv/v1/budget` | Campaign budget |
| POST | `/adv/v1/budget/deposit` | Top-up campaign budget |
| GET | `/adv/v1/upd` | Costs history |
| GET | `/adv/v1/payments` | Top-ups history |
| POST | `/adv/v0/normquery/stats` | Search clusters statistics |
| GET | `/adv/v3/fullstats` | Campaigns statistics |
| POST | `/adv/v1/normquery/stats` | Daily search clusters statistics |

### advert-media-api.wildberries.ru (Promotion token)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/adv/v1/count` | Media campaigns number |
| GET | `/adv/v1/adverts` | List of media campaigns |
| GET | `/adv/v1/advert` | Information about media campaign |
| POST | `/adv/v1/stats` | Media campaign statistics |

### dp-calendar-api.wildberries.ru (Prices and Discounts token)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/calendar/promotions` | Promotions list |
| GET | `/api/v1/calendar/promotions/details` | Promotions details |
| GET | `/api/v1/calendar/promotions/nomenclatures` | Products for promotion |
| POST | `/api/v1/calendar/promotions/upload` | Add product to promotion |

---

## Common Response Schemas

The following error schemas are reused across endpoints. Where a response section shows `→ See [Unauthorized (401)](#unauthorized-401)` or `→ See [Too Many Requests (429)](#too-many-requests-429)`, the full schema and example are defined here.

### ProblemResponse Schema

All `application/problem+json` error responses share this structure:

| Param | Type | Description |
| ----- | ---- | ----------- |
| title | string | Error title |
| detail | string | Error details |
| code | string | Internal error code |
| requestId | string | Unique request ID |
| origin | string | WB internal service ID |
| status | number | HTTP status code |
| statusText | string | Text of the HTTP status code |
| timestamp | string `<date-time>` | Request date and time |

### Unauthorized (401)

- Response Schema: application/problem+json
- Content type: application/json

```json
{
  "title": "unauthorized",
  "detail": "token problem; token is malformed: could not base64 decode signature: illegal base64 data at input byte 84",
  "code": "07e4668e--a53a3d31f8b0-[UK-oWaVDUqNrKG]; 03bce=277; 84bd353bf-75",
  "requestId": "7b80742415072fe8b6b7f7761f1d1211",
  "origin": "s2s-api-auth-catalog",
  "status": 401,
  "statusText": "Unauthorized",
  "timestamp": "2024-09-30T06:52:38Z"
}
```

### Too Many Requests (429)

- Response Schema: application/problem+json
- Content type: application/json

```json
{
  "title": "too many requests",
  "detail": "limited by c122a060-a7fb-4bb4-abb0-32fd4e18d489",
  "code": "07e4668e-ac2242c5c8c5-[UK-4dx7JUdskGZ]",
  "requestId": "9d3c02cc698f8b041c661a7c28bed293",
  "origin": "s2s-api-auth-catalog",
  "status": 429,
  "statusText": "Too Many Requests",
  "timestamp": "2024-09-30T06:52:38Z"
}
```

---

## Campaigns

To access the methods, use a token for the Promotion category

### Campaigns Lists

`/adv/v1/promotion/count`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v1/promotion/count`

#### Method description
Method allows to get campaigns lists grouped by type and status with information about last campaign change date.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s    | 5 requests | 200 ms | 5 requests |


##### Authorizations:

Header parameter name: `Authorization`

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200
- Response Schema: application/json
- Content type: application/json

```json
{
  "adverts": [
    {
      "type": 9,
      "status": 8,
      "count": 3,
      "advert_list": [
        {
          "advertId": 6485174,
          "changeTime": "2023-05-10T12:12:52.676254+03:00"
        },
        {
          "advertId": 6500443,
          "changeTime": "2023-05-10T17:08:46.370656+03:00"
        }
      ]
    }
  ],
  "all": 3
}
```

| Param | Type | Description |
| adverts	| array/null	| Campaign data	|
| all	| integer	| Total number of campaigns with all statuses and types	|

##### Campaign data

| Param | Type | Description |
| type | integer | Campaign type:

8 — campaign with standard bid (deprecated type)
9 — campaign with standard or custom bid. You can get the bid type with the Campaigns Information method, bid_type field |
| detail | integer | Campaign status |
| title | integer | Campaigns number |
| detail | array | Campaigns list |

##### Campaigns list

| Param | Type | Description |
| advertId | integer | Campaign ID |
| changeTime | string <date-time> | Date and time of the last campaign change |

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)

### Campaigns Information
`/api/advert/v2/adverts`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/api/advert/v2/adverts`


#### Method description

The method returns information about campaigns with standard or custom bid via statuses, payment types and IDs.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s	| 5 requests	| 200 ms	| 5 requests	|

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| ids	| string	| 
Example: ids=12345,23456,34567,45678,56789
Campaign IDs, maximum 50	|
| statuses	| string	| Example: statuses=-1,4,8
Campaign statuses:

-1 — deleted, the deletion process will be completed within 10 minutes
4 — ready to be launched
7 — completed
8 — declined
9 — active
11 — paused	|
| payment_type	| string	| Enum: "cpm" "cpc"
Payment type:

cpm — cost per mille
cpc — cost per click	|

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200
- Response Schema: application/json
- Content type: application/json

```json
{
  "adverts": [
    {
      "bid_type": "manual",
      "id": 567456457,
      "nm_settings": [
        {
          "bids_kopecks": {
            "recommendations": 0,
            "search": 0
          },
          "nm_id": 123456789,
          "subject": {
            "id": 52,
            "name": "кошельки"
          }
        },
        {
          "bids_kopecks": {
            "recommendations": 11200,
            "search": 11200
          },
          "nm_id": 987654321,
          "subject": {
            "id": 54,
            "name": "ювелирные кольца"
          }
        }
      ],
      "settings": {
        "name": "Кампания от 01.02.2024",
        "payment_type": "cpm",
        "placements": {
          "recommendations": false,
          "search": true
        }
      },
      "status": 7,
      "timestamps": {
        "created": "2024-02-01T09:57:38.500606+03:00",
        "deleted": "2024-02-05T14:29:32.633968+03:00",
        "started": "2024-02-05T12:38:10.212086+03:00",
        "updated": "2024-02-05T14:29:32.633968+03:00"
      }
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| adverts (required)	| array/null	| Campaigns	|


##### Campaigns

| Param | Type | Description |
| ----- | ---- | ----------- |
| bid_type (required)	| string	| Bid type: manual — standard bid, auto — custom bid	|
| id (required)	| integer <int64>	| Campaign ID	|
| nm_settings (required)	| array <AdvertNMsSettings>	| Product settings	|
| settings (required)	| object	| Campaign settings	|
| status (required)	| integer	| Enum: -1 4 7 8 9 11
Campaign status:

-1 — deleted, the deletion process will be completed within 10 minutes
4 — ready to be launched
7 — completed
8 — declined
9 — active
11 — campaign is paused	|
| timestamps (required)	| object <timestamps>	| Campaign timestamps	|

##### AdvertNMsSettings

| Param | Type | Description |
| ----- | ---- | ----------- |
| bids_kopecks (required)	| object (AdvertBidsKopecks)	| Bids, kopecks	|
| subject (required)	| object (AdvertSubject)	| Subject	|
| nm_id (required)	| integer <int64>	| WB article	|

##### AdvertBidsKopecks

| Param | Type | Description |
| ----- | ---- | ----------- |
| search (required)	| integer <int64>	| Bid in search	|
| recommendations (required)	| integer <int64>	| Bid in recommendations	|

##### AdvertSubject
| Param | Type | Description |
| ----- | ---- | ----------- |
| id (required)	| integer <int64>	| Subject ID	|
| name (required)	| string	| Subject name	|


##### AdvertSettings
| Param | Type | Description |
| ----- | ---- | ----------- |
| payment_type (required)	| string	| Enum: "cpm" "cpc"
Payment type:

cpm — cost per mille
cpc — cost per click	|
| name (required)	| string	| Campaign name	|
| placements (required)	| object	| Campaign placements	|


##### Placements
| Param | Type | Description |
| ----- | ---- | ----------- |
| search (required)	| boolean	| Placement in search:

false — disabled
true — enabled	|
| recommendations (required)	| boolean	| Placement in recommendations:

false — disabled
true — enabled	|


##### 400
- Response Schema: application/problem+json
- Content type: application/json

| Param | Type | Description |
| ----- | ---- | ----------- |
| title | string | Error details |
| detail | string | Error details |
| code | string | Internal error code |
| requestId | string | Unique request ID |
| origin | string | WB internal service ID |
| status | number | HTTP status code |
| statusText | string | Text of the HTTP status code |
| timestamp | string <date-time> | Request date and time |


```json
{
  "detail": "invalid payment_type value",
  "origin": "camp-api-public-cache",
  "request_id": "7e5cb1f106cc6e85b5b29eb2e8815da2",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)

### Campaigns Creation

> To access the methods, use a token for the Promotion category

#### Minimum Bids for Product Cards

`/api/advert/v1/bids/min`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/api/advert/v1/bids/min`


#### Method description

Method allows minimum bids for product cards in kopecks depending on the payment type and placements.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 min	| 20 requests	| 3 s	| 5 requests	| 

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "advert_id": 98765432,
  "nm_ids": [
    12345678,
    87654321
  ],
  "payment_type": "cpm",
  "placement_types": [
    "combined",
    "search",
    "recommendation"
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| advert_id required	| integer <int64>	| Campaign ID	|
| nm_ids required	| Array of integers <int64> [ 1 .. 100 ] characters [ items <int64 > ]	| WB articles list	|
| payment_type required	| string	| Enum: "cpm" "cpc"
Payment type:

- cpm — per mille
- cpc — per click	|
| placement_types (required)	| Array of strings	| Items Enum: "combined" "search" "recommendation"
Placements:

- search — search
- recommendation — recommendation
- combined — search and recommendation	|


#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200
- Response Schema: application/json
- Content type: application/json

```json
1234567
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| 	| integer	| Campaign ID	|


##### 400
- Response Schema: application/problem+json
- Content type: application/json

```json
"Нет доступных категорий для рк. Создайте новую кампанию для попадания в текущие категории"
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)

### Create Campaign
`/adv/v2/seacat/save-ad`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v2/seacat/save-ad`

#### Method description

The method creates campaign:

- with custom bid for promotion products in search and/or recommendations
- with standard bid for promotion products both in search and recommendations

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 min	| 5 requests	| 12 s	| 5 requests	| 

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "name": "Телефоны",
  "nms": [
    146168367,
    200425104
  ],
  "bid_type": "manual",
  "placement_types": [
    "search",
    "recommendations"
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| name	| string 	| Campaign name	|
| nms	| Array of integers	| Product cards for this campaign. You can retrieve available product cards using the product cards for campaigns method. Maximum of 50 products (nm)	|
| bid_type	| string	| Default: "manual"
Enum: "manual" "unified"
Bid type:

- unified — standard bid
- manual — custom bid	|
| payment_type	| string	| Default: "cpm"
Enum: "cpm" "cpc"
Payment type:

- cpm — cost per mille
- cpc — cost per click. When creating a campaign with this payment type, a minimum bid is automatically set	|
| placement_types	| Array of strings	| Default: ["search"]
Items Enum: "search" "recommendations"
Placements:

- search — search
- recommendations — recommendations

Specify for campaign with custom bid only	|


#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200
- Response Schema: application/json
- Content type: application/json

```json
1234567
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| 	| integer	| Campaign ID	|

##### 400
- Response Schema: application/problem+json
- Content type: application/json

| Param | Type | Description |
| ----- | ---- | ----------- |
| 	| string 	| Error details	|


```json
{
  "detail": "invalid payment_type value",
  "origin": "camp-api-public-cache",
  "request_id": "7e5cb1f106cc6e85b5b29eb2e8815da2",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Subjects for Campaigns
`/adv/v1/supplier/subjects`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v1/supplier/subjects`

#### Method description

Returns subjects product cards from which are available for all campaigns

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 12 s	| 1 requests	| 12 s	| 5 requests	| 

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| payment_type	| string	| Enum: "cpm" "cpc"
Payment type:

cpm — cost per mille
cpc — cost per click	|


#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **401** | Unauthorized |
| **404** | Not Found |
| **429** | Too many requests |

#### Response samples

##### 200
- Response Schema: application/json
- Content type: application/json

```json
[
  {
    "name": "3D очки",
    "id": 2560,
    "count": 1899
  }
]
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| id	| integer	| Subject ID	|
| name	| string	| Subject name	|
| count	| integer	| Number of WB articles (`nmId`) in this subject	|

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Product Cards for Campaigns
`/adv/v2/supplier/nms`


- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v2/supplier/nms`

#### Method description
Returns product cards that are available for all campaigns.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 min	| 5 requests	| 12 s	| 5 requests	| 

#### Authorizations:

Header parameter name: `Authorization`


#### Request Body schema (required): `application/json`

```json
[
  123,
  456,
  765,
  321
]
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| 	| array <integer> 	| ID of subjects to get product cards	|

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200
- Response Schema: application/json
- Content type: application/json

```json
[
  {
    "title": "Плед",
    "nm": 146168367,
    "subjectId": 765
  }
]
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| title | string | Error details |
| nm | integer | WB article ID |
| subjectId | integer | Subject ID |


##### 400

- Content type: text/plain

```txt
Error processing request body
```


```json
"Нет доступных категорий для рк. Создайте новую кампанию для попадания в текущие категории"
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


## Campaigns Management
To access the methods, use a token for the Promotion category

### Delete Campaign
`/adv/v0/delete`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v0/delete`

#### Method description
The method allows to delete campaigns in the status 4 — ready to launch.

After deleting, the campaign will be in -1 status for a while.

It takes between 3 and 10 minutes to completely delete the campaign.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s	| 5 requests	| 200 ms	| 5 requests	| 


#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| id	| integer	| Campaign ID	|


#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200
- Response Schema: application/json
- Content type: application/json

```json
[
  {
    "title": "Плед",
    "nm": 146168367,
    "subjectId": 765
  }
]
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| title | string | Error details |
| nm | integer | WB article ID |
| subjectId | integer | Subject ID |


##### 400

- Response Schema: application/json
- Content type: application/json

```json
{
"error": "Invalid campaign identifier"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)

### Rename Campaign
`/adv/v0/rename`


- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v0/rename`

#### Method description
The method allows to rename a campaign.


Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s	| 5 requests	| 200 ms	| 5 requests	| 


#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "advertId": 2233344,
  "name": "newname"
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| advertId (required) 	| integer 	| ID of the campaign where the name is changing 	|
| name (required) 	| string 	| New name (max 100 characters) 	|


#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **422** | Error processing request parameters |
| **429** | Too many requests |

#### Response samples

##### 400

- Content type: text/plain

##### InvalidRcIdAdv

```txt
Incorrect campaign identifier (RC ID)
```

##### IncorrectName

```txt
Incorrect seller identifier
```

##### IncorrectSupplierIdAdv

```txt
Incorrect campaign identifier (RC ID)
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 422

- Content type: text/plain

##### RequestBodyProcessErrorAdv

```txt
{
"Error processing request body
}
```

##### RequestBodyProcessErrorAdv

```txt
{
"Error changing the campaign name"
}
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)

### Launch Campaign
`/adv/v0/start`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v0/start`

#### Method description
The method allows to run campaigns that are in statuses 4 — ready to launch or 11 — paused campaign.
To run a campaign, check its budget. If the budget is insufficient, replenish it.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Example: `id=1234`<br>Campaign ID |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **422** | Status not changed |
| **429** | Too many requests |

#### Response samples

##### 400

- Content type: application/json

###### IncorrectId

```json
{
  "error": "Invalid Advert: invalid advert"
}
```

###### AdvertNotFound

```json
{
  "error": "AdvertChangeStatus: Not Found: advert not found"
}
```

###### LowBudget

```json
{
  "error": "AdvertChangeStatus: Low Budget: not enough budget"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 422

- Content type: text/plain

```txt
Campaign status not changed
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Pause Campaign
`/adv/v0/pause`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v0/pause`

#### Method description
Campaign in status 9 — active — can be paused.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Example: `id=1234`<br>Campaign ID |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **422** | Status not changed |
| **429** | Too many requests |

#### Response samples

##### 400

- Content type: application/json

###### IncorrectId

```json
{
  "error": "Invalid Advert: invalid advert"
}
```

###### AdvertNotFound

```json
{
  "error": "AdvertChangeStatus: Not Found: advert not found"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 422

- Content type: text/plain

```txt
Campaign status not changed
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Stop Campaign
`/adv/v0/stop`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v0/stop`

#### Method description
The method allows to end campaigns in statuses:

- 4 — ready to launch
- 9 — active
- 11 — paused

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Example: `id=1234`<br>Campaign ID |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **422** | Status not changed |
| **429** | Too many requests |

#### Response samples

##### 400

- Content type: application/json

###### IncorrectId

```json
{
  "error": "Invalid Advert: invalid advert"
}
```

###### AdvertNotFound

```json
{
  "error": "AdvertChangeStatus: Not Found: advert not found"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 422

- Content type: text/plain

```txt
Campaign status not changed
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)

### Changing Placements in Campaigns with Custom Bid
`/adv/v0/auction/placements`

- Method: `PUT`
- URL: `https://advert-api.wildberries.ru/adv/v0/auction/placements`

#### Method description
The method allows you to change placements in campaigns with custom bid and per mille payment model — cpm.

For campaigns in statuses 4, 9 and 11.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 1 request | 1 s | 1 request |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "placements": [
    {
      "advert_id": 12345,
      "placements": {
        "search": true,
        "recommendations": true
      }
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `placements` (required) | Array of objects `<= 50 items` `<CampaignPlacements>` | Placements in campaigns |

##### CampaignPlacements

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer `<int64>` | Campaign ID |
| `placements` (required) | object `<Placements>` | Placements |

##### Placements

| Param | Type | Description |
| ----- | ---- | ----------- |
| `search` (required) | boolean | Placement in search:<br>`false` — disabled<br>`true` — enabled |
| `recommendations` (required) | boolean | Placement in recommendations:<br>`false` — disabled<br>`true` — enabled |

#### Responses

| Code | Status |
| --- | --- |
| **204** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 400

- Content type: application/json

###### BadRequest

```json
{
  "detail": "can not deserialize response body",
  "origin": "camp-api-public-cache",
  "request_id": "9a929a81ea9dc1601fcc4be81f32c1cb",
  "status": 400,
  "title": "invalid payload"
}
```

###### BadAdvertPaymentType

```json
{
  "detail": "advert 12345 has payment type cpc, placements cannot be changed",
  "origin": "camp-api-public-cache",
  "request_id": "e53addfabe9274d5b8f77272ca085ac4",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Changing Campaigns Bids
`/api/advert/v1/bids`

- Method: `PATCH`
- URL: `https://advert-api.wildberries.ru/api/advert/v1/bids`

#### Method description
The method changes the bids of product cards by WB articles in campaigns:

- with standard bid
- with custom bid
- with a cpc payment model — per click

For campaigns in statuses `4`, `9` and `11`.

Specify the placement in the request parameter `placement`:
- `combined` — in search and recommendations for campaigns with standard bid
- `search` or `recommendations` — in search or recommendations for campaigns with custom bid

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "bids": [
    {
      "advert_id": 12345,
      "nm_bids": [
        {
          "nm_id": 13335157,
          "bid_kopecks": 250,
          "placement": "recommendations"
        }
      ]
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `bids` (required) | Array of objects `<= 50 items` `<CampaignBids>` | Bids in campaigns, kopecks |

##### CampaignBids

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer `<int64>` | Campaign ID |
| `nm_bids` (required) | Array of objects `<= 50 items` `<Bids>` | Bids |

##### Bids

| Param | Type | Description |
| ----- | ---- | ----------- |
| `nm_id` (required) | integer `<int64>` | WB article |
| `bid_kopecks` (required) | integer `<int64>` | Bid, kopecks |
| `placement` (required) | string | Enum: `"search"` `"recommendations"` `"combined"`<br>Placement:<br>- `search` — in search (for campaigns with custom bid)<br>- `recommendations` — in recommendations (for campaigns with custom bid)<br>- `combined` — in search and recommendations (for campaigns with standard bid) |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "bids": [
    {
      "advert_id": 12345,
      "nm_bids": [
        {
          "nm_id": 13335157,
          "bid_kopecks": 250,
          "placement": "recommendations"
        }
      ]
    }
  ]
}
```

##### 400

- Content type: application/json

```json
{
  "detail": "wrong bid value: 3; min: 150",
  "origin": "camp-api-public-cache",
  "request_id": "9a929a81ea9dc1601fcc4be81f32c1cb",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)



### Changing the List of Product Cards in Campaigns
`/adv/v0/auction/nms`

- Method: `PATCH`
- URL: `https://advert-api.wildberries.ru/adv/v0/auction/nms`

#### Method description
The method allows you to add and remove product cards in campaigns.

For campaigns in statuses `4`, `9` and `11`.

The current minimum bid is set for the added products.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 1 request | 1 s | 1 request |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "nms": [
    {
      "advert_id": 12345,
      "nms": {
        "add": [
          11111111,
          44444444
        ],
        "delete": [
          55555555
        ]
      }
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `nms` (required) | Array of objects `<= 20 items` `<CampaignNms>` | Product cards in campaigns |

##### CampaignNms

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer `<int64>` | Campaign ID |
| `nms` (required) | object `<CampaignNmsChanges>` | Product cards. Maximum of 50 products per campaign |

##### CampaignNmsChanges

| Param | Type | Description |
| ----- | ---- | ----------- |
| `add` | Array of integers | The product cards that need to be added |
| `delete` | Array of integers | The product cards that need to be deleted |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "nms": [
    {
      "advert_id": 12345,
      "nms": {
        "added": [
          11111111,
          44444444
        ],
        "deleted": [
          55555555
        ]
      }
    }
  ]
}
```

##### 400

- Content type: application/json

```json
{
  "detail": "nomenclature 13335157 cannot be both added and deleted for advert 27247695",
  "origin": "camp-api-public-cache",
  "request_id": "6023d2950af564838f9b44a279d2140c",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Recommended bids for items and search clusters
`/api/advert/v0/bids/recommendations`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/api/advert/v0/bids/recommendations`

#### Method description
The method returns recommended bids for items and search clusters of the campaign. Only for campaigns with cpm payment type — cost per mille.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 min | 5 requests | 12 s | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `nmId` (required) | integer `<int64>` | Example: `nmId=123456789`<br>WB article |
| `advertId` (required) | integer `<int64>` | Example: `advertId=987654321`<br>Campaign ID |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "advertId": 987654321,
  "base": {
    "competitiveBid": {
      "bidKopecks": 39500
    },
    "leadersBid": {
      "bidKopecks": 66900
    },
    "top2": {
      "bidKopecks": 0
    }
  },
  "nmId": 123456789,
  "normQueries": [
    {
      "normQuery": "футболка",
      "reachMax": {
        "bidKopecks": 50500,
        "bidKopecksMin": 49500
      },
      "reachMedium": {
        "bidKopecks": 32000
      },
      "reachMin": {
        "bidKopecks": 32000
      }
    }
  ]
}
```

##### 400

- Content type: text/plain

###### IncorrectTypeAdv

```txt
Incorrect value for the `type` parameter
```

###### IncorrectSupplierIdAdv

```txt
Incorrect seller identifier
```

###### IncorrectUsingMethods

```txt
To obtain information, provide either a list of campaigns or a set of filters
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


## Search Clusters

> To access the methods, use a token for the Promotion category

**Search Clusters**

Request cluster is a grouped list of requests that buyers use to search for products on WB. The cluster includes:

- synonyms
- requests in different genders
- requests with typos
- different word forms
- phrases with similar meanings

For example, the `men t-shirt` cluster will also include requests like `mren t-shirt`, `men t-shirts with sleeves`, `man t-shirts`, and other similar phrases.


To get clusters that have already had impressions, use the `search clusters statistics` method.


You can `set` or `delete` bids for campaigns with custom bids. Bids are individual for each search cluster.


**Exclusions**

Set minus phrases to exclude request clusters from campaigns. The product will not be promoted for minus phrases.

### List of Search Clusters Bids
`/adv/v0/normquery/get-bids`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v0/normquery/get-bids`

#### Method description
The method returns a list of search clusters with bids by:

- campaign IDs
- WB articles

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "items": [
    {
      "advert_id": 1825035,
      "nm_id": 983512347
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `items` (required) | Array of objects `<= 100 items` `<BidRequestItem>` | Campaign/article pairs to query |

##### BidRequestItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer | Campaign ID |
| `nm_id` (required) | integer | WB article |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **403** | Access denied |
| **429** | Too many requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "bids": [
    {
      "advert_id": 1825035,
      "bid": 700,
      "nm_id": 983512347,
      "norm_query": "Фраза 1"
    },
    {
      "advert_id": 1825035,
      "bid": 9000,
      "nm_id": 983512347,
      "norm_query": "Фраза 2"
    }
  ]
}
```

##### 400

- Content type: application/json

```json
{
  "detail": "invalid payment_type value",
  "origin": "camp-api-public-cache",
  "request_id": "7e5cb1f106cc6e85b5b29eb2e8815da2",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 403

- Content type: application/json

```json
{
  "detail": "norm_query API not available",
  "origin": "camp-api-public-cache",
  "request_id": "60aaf2bc6164e84a9399fae9565b568a",
  "status": 403,
  "title": "request forbidden"
}
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Set Bids for Search Clusters
`/adv/v0/normquery/bids`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v0/normquery/bids`

#### Method description
The method sets the bids for search clusters.
You can use this method only for campaigns with:

- custom bid
- a `cpm` payment model — per displays

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 2 requests | 500 ms | 4 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "bids": [
    {
      "advert_id": 1825035,
      "nm_id": 983512347,
      "norm_query": "Фраза 1",
      "bid": 1000
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `bids` (required) | Array of objects `<= 100 items` `<BidRequestItem>` | Bids to set |

##### BidRequestItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer | Campaign ID |
| `nm_id` (required) | integer | WB article |
| `norm_query` (required) | string | Search cluster |
| `bid` (required) | integer | Bid per mille, ₽ |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **403** | Access denied |
| **429** | Too many requests |

#### Response samples

##### 400

- Content type: application/json

```json
{
  "detail": "invalid payment_type value",
  "origin": "camp-api-public-cache",
  "request_id": "7e5cb1f106cc6e85b5b29eb2e8815da2",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 403

- Content type: application/json

```json
{
  "detail": "norm_query API not available",
  "origin": "camp-api-public-cache",
  "request_id": "60aaf2bc6164e84a9399fae9565b568a",
  "status": 403,
  "title": "request forbidden"
}
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Delete Bids from Search Clusters
`/adv/v0/normquery/bids`

- Method: `DELETE`
- URL: `https://advert-api.wildberries.ru/adv/v0/normquery/bids`

#### Method description
The method deletes the bids from search clusters.
You can use this method only for campaigns with:

- custom bid
- a `cpm` payment model — per displays

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "bids": [
    {
      "advert_id": 1825035,
      "nm_id": 983512347,
      "norm_query": "Фраза 1",
      "bid": 1000
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `bids` (required) | Array of objects `<= 100 items` `<BidsRequestItem>` | Bids to delete |

##### BidsRequestItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer | Campaign ID |
| `nm_id` (required) | integer | WB article |
| `norm_query` (required) | string | Search cluster |
| `bid` (required) | integer | Bid per mille, ₽ |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **403** | Access denied |
| **429** | Too many requests |

#### Response samples

##### 400

- Content type: application/json

```json
{
  "detail": "invalid payment_type value",
  "origin": "camp-api-public-cache",
  "request_id": "7e5cb1f106cc6e85b5b29eb2e8815da2",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 403
→ See [403 — norm_query API not available](#set-bids-for-search-clusters) (same as Set Bids)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### List of Campaign Minus Phrases
`/adv/v0/normquery/get-minus`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v0/normquery/get-minus`

#### Method description
The method returns a list of minus phrases by:

- campaign IDs
- WB articles

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "items": [
    {
      "advert_id": 1825035,
      "nm_id": 983512347
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `items` (required) | Array of objects `<= 100 items` `<NormQueryMinusRequestItem>` | Campaign/article pairs to query |

##### NormQueryMinusRequestItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer | Campaign ID |
| `nm_id` (required) | integer | WB article |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **403** | Access denied |
| **429** | Too many requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "items": [
    {
      "advert_id": 1825035,
      "nm_id": 983512347,
      "norm_queries": ["Фраза 1", "Фраза 2"]
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `items` | Array of objects `<NormQueryMinusResponseItem>` | List of minus phrases |

##### NormQueryMinusResponseItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` | integer | Campaign ID |
| `nm_id` | integer | WB article |
| `norm_queries` | Array of strings | List of minus phrases |

##### 400
No specific schema — bad request.

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 403
→ See [403 — norm_query API not available](#set-bids-for-search-clusters)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Setting and Deleting Minus Phrases
`/adv/v0/normquery/set-minus`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v0/normquery/set-minus`

#### Method description
The method sets and deletes the minus phrases in campaigns with standard and custom bid.

> Sending an empty array deletes all minus phrases

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "advert_id": 1825035,
  "nm_id": 983512347,
  "norm_queries": [
    "Фраза 1"
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer | Campaign ID |
| `nm_id` (required) | integer | WB article |
| `norm_queries` (required) | Array of strings `<= 1000 items` | Minus phrases to set; empty array deletes all |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **403** | Access denied |
| **429** | Too many requests |

#### Response samples

##### 400
No specific schema — bad request.

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 403
→ See [403 — norm_query API not available](#set-bids-for-search-clusters)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Active and Inactive Search Cluster Lists
`/adv/v0/normquery/list`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v0/normquery/list`

#### Method description
Returns lists of active and inactive search clusters with at least 100 views.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 5 requests | 200 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "items": [
    {
      "advertId": 123456789,
      "nmId": 987654321
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `items` (required) | Array of objects `<= 100 items` `<NormQueryListRequestItem>` | Campaign/article pairs to query |

##### NormQueryListRequestItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advertId` (required) | integer `<int64>` | Campaign ID |
| `nmId` (required) | integer `<int64>` | WB article |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "items": [
    {
      "advertId": 123456789,
      "nmId": 987654321,
      "normQueries": {
        "active": null,
        "excluded": [
          "бест трикотаж",
          "горы футболка для мужчин",
          "футболка поло мужская"
        ]
      }
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `items` | Array of objects `<NormQueryListResponseItem>` | Search cluster lists per campaign/article |

##### NormQueryListResponseItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advertId` | integer `<int64>` | Campaign ID |
| `nmId` | integer `<int64>` | WB article |
| `normQueries` | object `<ListResponseItemNormQueries>` | Search clusters |

##### ListResponseItemNormQueries

| Param | Type | Description |
| ----- | ---- | ----------- |
| `active` | Array of strings or null | Active search clusters |
| `excluded` | Array of strings or null | Inactive search clusters |

##### 400
No specific schema — bad request.

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


## Finances

> To access the methods, use a token for the Promotion category

### Balance
`/adv/v1/balance`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v1/balance`

#### Method description
The method allows to get information about the seller's net, balance and bonuses.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 1 request | 1 s | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too many requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "balance": 11083,
  "net": 0,
  "bonus": 15187,
  "cashbacks": [
    {
      "sum": 10672,
      "percent": 50,
      "expiration_date": "2026-04-17T10:46:02.176174Z"
    }
  ]
}
```

##### 400

- Content type: application/json

```json
"Incorrect seller identifier"
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Campaign Budget
`/adv/v1/budget`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v1/budget`

#### Method description
The method allows to get information about the budget of a campaign.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 4 requests | 250 ms | 4 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Example: `id=1`<br>Campaign ID |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "cash": 0,
  "netting": 0,
  "total": 500
}
```

##### 400

- Content type: text/plain

```txt
Campaign does not belong to the seller
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Top-up of the Campaign Budget
`/adv/v1/budget/deposit`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v1/budget/deposit`

#### Method description
The method tops up the campaign budget.
To launch the campaign after topping up the budget, use the Launch campaign method.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 1 request | 1 s | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Example: `id=1234567`<br>Campaign ID |

#### Request Body schema (required): `application/json`

```json
{
  "sum": 5000,
  "cashback_sum": 1000,
  "cashback_percent": 50,
  "type": 1,
  "return": true
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `sum` | integer | Budget top-up amount |
| `cashback_sum` | integer or null | Top-up budget sum paid with promo bonuses.<br>You can top up only a certain percentage of the amount, indicated in the `percent` field of the response from the method for getting balance.<br>Promo bonuses are only applicable to these top-up sources:<br>- `0` — account<br>- `1` — balance sheet |
| `cashback_percent` | integer or null | The percentage of the top-up amount that can be paid with promo bonuses. You need to specify the value of the percent field from the response for the method for getting balance.<br>If you specified `cashback_sum`, the `cashback_percent` parameter becomes required |
| `type` | integer | Type of top-up source:<br>- `0` — Account<br>- `1` — Balance<br>- `3` — Bonuses |
| `return` | boolean | Response return flag (`true` means updated campaign budget size will be returned in the response, `false` or empty means nothing will be returned). |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

> Response when return is true

```json
{
  "total": 7289
}
```

##### 400

- Content type: application/json

DepositAmountMultiple50

```json
{
  "error": "Сумма пополнения должна быть кратна 50 руб"
}
```

MinimumDepositAmountIs500

```json
{
  "error": "Минимальная сумма пополнения 1000 рублей"
}
```

IncorrectType

```json
{
  "error": "Invalid Params: cashback can not be used with such type"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Receiving Costs History
`/adv/v1/upd`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v1/upd`

#### Method description
The method allows to get a costs history

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 1 request | 1 s | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `from` (required) | string \<date\> | Example: `from=2023-07-31`<br>Beginning of the interval |
| `to` (required) | string \<date\> | Example: `to=2023-08-02`<br>End of interval. (Minimum interval is 1 day, maximum is 31) |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
[
  {
    "updNum": 0,
    "updTime": "2023-07-31T12:12:54.060536+03:00",
    "updSum": 24,
    "advertId": 3355881,
    "campName": "лук лучок",
    "advertType": 6,
    "paymentType": "Баланс",
    "advertStatus": 9
  },
  {
    "updNum": 0,
    "updTime": null,
    "updSum": 107,
    "advertId": 3366882,
    "campName": "золотая луковица",
    "advertType": 8,
    "paymentType": "Счет",
    "advertStatus": 11
  }
]
```

##### 400

- Content type: text/plain

```txt
Incorrect seller identifier
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Receiving the History of Account Top-ups
`/adv/v1/payments`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v1/payments`

#### Method description
The method allows you to get a history of top-ups.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 1 request | 1 s | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `from` | string \<date\> | Example: `from=2023-07-31`<br>Beginning of the interval |
| `to` | string \<date\> | Example: `to=2023-08-02`<br>End of interval. (Minimum interval is 1 day, maximum is 31) |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **204** | Transaction history not found |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
[
  {
    "id": 1036666,
    "date": "2022-02-04T09:06:47.985843Z",
    "sum": 600,
    "type": 0,
    "statusId": 1,
    "cardStatus": ""
  },
  {
    "id": 55261296,
    "date": "2023-04-13T10:07:42",
    "sum": 1500,
    "type": 3,
    "statusId": 1,
    "cardStatus": "succeeded"
  }
]
```

##### 400

- Content type: application/json

```json
"Incorrect seller identifier"
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


## Media

> To access the methods, use a token for the Promotion category

### Media Campaigns Number
`/adv/v1/count`

- Method: `GET`
- URL: `https://advert-media-api.wildberries.ru/adv/v1/count`

#### Method description
Method allows you to get the number of the seller's media campaigns.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 10 requests | 100 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "all": 6,
  "adverts": {
    "type": 2,
    "status": 7,
    "count": 2
  }
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### List of Media Campaigns
`/adv/v1/adverts`

- Method: `GET`
- URL: `https://advert-media-api.wildberries.ru/adv/v1/adverts`

#### Method description
The method allows to get the list of media campaigns of the seller

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 10 requests | 100 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `status` | integer | Example: `status=1`<br>Media campaign status:<br>- `1` — template<br>- `2` — moderation<br>- `3` — rejected (with the possibility to resubmit for moderation)<br>- `4` — ready for launch<br>- `5` — scheduled<br>- `6` — running<br>- `7` — completed<br>- `8` — declined<br>- `9` — paused by seller<br>- `10` — paused due to daily limit<br>- `11` — paused |
| `type` | integer | Example: `type=1`<br>Media campaign type:<br>- `1` — daily basis<br>- `2` — views basis |
| `limit` | integer | Example: `limit=1`<br>Number of campaigns in the response |
| `offset` | integer | Example: `offset=1`<br>Offset relative to the first media campaign |
| `order` | string | Example: `order=id`<br>The order in which the response is displayed:<br>- `create` — by time of media campaign creation<br>- `id` — by ID of media campaign creation |
| `direction` | string | Example: `direction=desc`<br>Sorting order:<br>- `desc` — upward<br>- `asc` — smaller to larger |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **204** | Media campaigns not found |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
[
  {
    "advertId": 123456,
    "name": "тост",
    "brand": "brand",
    "type": 2,
    "status": 8,
    "createTime": "2023-03-25T20:35:57.116943+03:00"
  },
  {
    "advertId": 54321,
    "name": "тест",
    "brand": "brandname",
    "type": 1,
    "status": 7,
    "createTime": "2023-07-24T16:48:20.935599+03:00",
    "endTime": "2023-07-25T20:35:50.104978Z"
  }
]
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advertId` | integer | Media campaign ID |
| `name` | string | Media campaign name |
| `brand` | string | Brand name |
| `type` | integer | Media campaign type:<br>- `1` — daily basis<br>- `2` — views basis |
| `status` | integer | Media campaign status:<br>- `1` — template<br>- `2` — moderation<br>- `3` — rejected (with the possibility to resubmit for moderation)<br>- `4` — ready for launch<br>- `5` — scheduled<br>- `6` — running<br>- `7` — completed<br>- `8` — declined<br>- `9` — paused by seller<br>- `10` — paused due to daily limit<br>- `11` — paused |
| `createTime` | string \<date-time\> | Time of media campaign creation |
| `endTime` | string \<date-time\> | Time of completion of the media campaign |

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Information About Media Campaign
`/adv/v1/advert`

- Method: `GET`
- URL: `https://advert-media-api.wildberries.ru/adv/v1/advert`

#### Method description
The method allows to get information about a media campaign

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 10 requests | 100 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Example: `id=23569`<br>Media campaign ID |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **204** | Media campaign not found |
| **401** | Unauthorized |
| **429** | Too Many Requests |


#### Response samples

##### 200

- Content type: application/json

```json
{
  "advertId": 23569,
  "name": "Реклама денег принеси",
  "brand": "Plank",
  "type": 2,
  "status": 11,
  "createTime": "2023-07-19T11:13:41.195138+03:00",
  "extended": {
    "reason": "Для возобновления показов пополните бюджет медиакампании",
    "expenses": 10000,
    "from": "2023-07-19T12:05:35.847348Z",
    "to": "2123-07-20T08:14:13.079176+03:00",
    "updated_at": "2023-07-21T13:25:31.129766+03:00",
    "price": 0,
    "budget": 0,
    "operation": 1,
    "contract_id": 0
  },
  "items": [
    {
      "id": 68080,
      "name": "Унисон",
      "status": 7,
      "place": 2,
      "budget": 650000,
      "daily_limit": 500,
      "category_name": "Главная",
      "cpm": 351,
      "url": "https://www.wildberries.ru/promotions/ssylka-na-akciyou",
      "advert_type": 1,
      "created_at": "2023-11-01T15:40:46.86165+03:00",
      "updated_at": "2023-11-08T23:44:33.248229+03:00",
      "date_from": "2023-11-01T16:05:22.286002Z",
      "date_to": "2023-11-09T17:27:32.745869+03:00",
      "nms": [
        123456,
        11111111
      ],
      "bottomText1": "string",
      "bottomText2": "string",
      "message": "string",
      "additionalSettings": 1,
      "receiversCount": 1,
      "subject_id": 6945,
      "subject_name": "Бельё",
      "action_name": "Распродажа! Создай себе домашний уют!",
      "show_hours": [
        {
          "From": 7,
          "To": 8
        }
      ],
      "Erid": "string"
    }
  ]
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


## Statistics

> To access the methods, use a token for the Promotion category

### Search Clusters Statistics
`/adv/v0/normquery/stats`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v0/normquery/stats`

#### Method description
The method returns statistics for search clusters over a specified period.
You can use this method only for campaigns with a `cpm` payment model — for displays.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 min | 10 requests | 6 s | 20 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "from": "2025-10-07",
  "to": "2025-10-08",
  "items": [
    {
      "advert_id": 1825035,
      "nm_id": 983512347
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `from` (required) | string \<date\> | Period start date |
| `to` (required) | string \<date\> | Period end date |
| `items` (required) | Array of objects \<= 100 items \<CampaignItem\> | |

##### CampaignItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advert_id` (required) | integer | Campaign ID |
| `nm_id` (required) | integer | WB article |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **403** | Access Denied |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "stats": [
    {
      "advert_id": 1825035,
      "nm_id": 983512347,
      "stats": [
        {
          "atbs": 68,
          "avg_pos": 3.6,
          "clicks": 2090,
          "cpc": 471,
          "cpm": 813,
          "ctr": 107.23,
          "norm_query": "Фраза 1",
          "orders": 19,
          "views": 1949
        },
        {
          "atbs": 36,
          "avg_pos": 3.9,
          "clicks": 1847,
          "cpc": 278,
          "cpm": 445,
          "ctr": 96.4,
          "norm_query": "Фраза 2",
          "orders": 28,
          "views": 1916
        }
      ]
    }
  ]
}
```

> Note: Response contains one entry per search cluster. Array truncated for brevity — all entries share the same schema.

##### 400

- Content type: application/json

```json
{
  "detail": "invalid payment_type value",
  "origin": "camp-api-public-cache",
  "request_id": "7e5cb1f106cc6e85b5b29eb2e8815da2",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 403
→ See [403 — norm_query API not available](#set-bids-for-search-clusters)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)

### Campaigns Statistics
`/adv/v3/fullstats`

- Method: `GET`
- URL: `https://advert-api.wildberries.ru/adv/v3/fullstats`

#### Method description

The method generates statistics for campaigns, regardless of their type.

The maximum period in a request is 31 days.

For campaigns in statuses `7`, `9` and `11`.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 min | 3 requests | 20 s | 1 request |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `ids` (required) | string | Example: `ids=22161678,28449281,28155229`<br>Campaign IDs, maximum 50 values |
| `beginDate` (required) | string \<date\> | Example: `beginDate=2025-09-07`<br>Start date for the interval |
| `endDate` (required) | string \<date\> | Example: `endDate=2025-09-08`<br>End date for the interval |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

> Response is an array of campaign stats. Each campaign contains `days[]`, each day contains `apps[]` (by appType), each app contains `nms[]` (by product). Structure shown with 1 campaign, 1 day, 2 app types:

```json
[
  {
    "advertId": 22161678,
    "atbs": 9,
    "boosterStats": [
      {
        "avg_position": 24,
        "date": "2025-09-07",
        "nm": 221725278
      }
    ],
    "canceled": 0,
    "clicks": 139,
    "cpc": 4.76,
    "cr": 0,
    "ctr": 10.12,
    "days": [
      {
        "apps": [
          {
            "appType": 1,
            "atbs": 0,
            "canceled": 0,
            "clicks": 1,
            "cpc": 10.19,
            "cr": 0,
            "ctr": 4.76,
            "nms": [
              {
                "atbs": 0,
                "canceled": 0,
                "clicks": 1,
                "cpc": 10.19,
                "cr": 0,
                "ctr": 4.76,
                "name": "постер 2",
                "nmId": 221725278,
                "orders": 0,
                "shks": 0,
                "sum": 10.19,
                "sum_price": 0,
                "views": 21
              }
            ],
            "orders": 0,
            "shks": 0,
            "sum": 10.19,
            "sum_price": 0,
            "views": 21
          },
          {
            "appType": 32,
            "atbs": 1,
            "canceled": 0,
            "clicks": 54,
            "cpc": 4.26,
            "cr": 0,
            "ctr": 11.37,
            "nms": [
              {
                "atbs": 1,
                "canceled": 0,
                "clicks": 54,
                "cpc": 4.26,
                "cr": 0,
                "ctr": 11.37,
                "name": "постер 2",
                "nmId": 221725278,
                "orders": 0,
                "shks": 0,
                "sum": 230.08,
                "sum_price": 0,
                "views": 475
              }
            ],
            "orders": 0,
            "shks": 0,
            "sum": 230.08,
            "sum_price": 0,
            "views": 475
          }
        ],
        "atbs": 2,
        "canceled": 0,
        "clicks": 75,
        "cpc": 5.05,
        "cr": 0,
        "ctr": 9.57,
        "date": "2025-09-07T00:00:00Z",
        "orders": 0,
        "shks": 0,
        "sum": 378.49,
        "sum_price": 0,
        "views": 784
      }
    ],
    "orders": 0,
    "shks": 0,
    "sum": 661.25,
    "sum_price": 0,
    "views": 1373
  }
]
```

> Note: Full response contains one entry per campaign, multiple days per campaign, multiple app types per day, and multiple nms per app type. All levels share the same field set (atbs, canceled, clicks, cpc, cr, ctr, orders, shks, sum, sum_price, views). The `boosterStats` array contains one entry per date+nm combination.

##### 400

- Content type: application/json

```json
{
  "detail": "invalid ids",
  "origin": "camp-api-public-cache",
  "request_id": "40a229f3775b03585b65420c787aaebe",
  "status": 400,
  "title": "invalid payload"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Media Campaign Statistics
`/adv/v1/stats`

- Method: `POST`
- URL: `https://advert-media-api.wildberries.ru/adv/v1/stats`

#### Method description
The method allows to get statistics of WB Media campaigns

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 s | 10 requests | 100 ms | 10 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

Array of `[ 1 .. 100 ]` items. One of `RequestWithDate`, `RequestWithInterval`, `RequestWithCampaignID`.

##### RequestWithoutParam

```json
[
  {
    "id": 107024
  }
]
```

##### RequestWithDate

```json
[
  {
    "id": 8960367,
    "dates": [
      "2023-10-07",
      "2023-10-06"
    ]
  }
]
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Campaign ID |
| `dates` (required) | Array of strings \<date\> | Dates for which information needs to be provided |

##### RequestWithInterval

```json
[
  {
    "id": 8960367,
    "interval": {
      "begin": "2023-10-08",
      "end": "2023-10-10"
    }
  }
]
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Campaign ID |
| `interval` (required) | object | The time period for which information needs to be provided |
| `interval.begin` | string \<date\> | Beginning of the requested period |
| `interval.end` | string \<date\> | End of the requested period |

##### RequestWithCampaignID

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` (required) | integer | Campaign ID |

##### RequestAggregate

```json
[
  {
    "id": 107024,
    "interval": {
      "begin": "2023-10-21",
      "end": "2023-10-21"
    }
  },
  {
    "id": 107024,
    "dates": [
      "2023-10-22",
      "2023-10-26"
    ]
  }
]
```

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

> All response variants share the same `stats[]` item structure. The wrapper differs by request type (interval, dates, or no param). One representative example shown:

RespStatMediaInterval

```json
[
  {
    "interval": {
      "begin": "2023-10-21",
      "end": "2023-10-25"
    },
    "stats": [
      {
        "item_id": 62237,
        "item_name": "Gloria Jeans",
        "category_name": "Детям",
        "advert_type": 1,
        "place": 2,
        "views": 11849,
        "clicks": 209,
        "cr": 0.48,
        "ctr": 1.76,
        "date_from": "2023-10-21T00:00:00+03:00",
        "date_to": "2023-10-27T23:59:59+03:00",
        "subject_name": "Одежда",
        "atbs": 4,
        "orders": 1,
        "price": 175000,
        "cpc": 837.32,
        "status": 6,
        "daily_stats": [
          {
            "date": "2023-10-21T00:00:00+03:00",
            "app_type_stats": [
              {
                "app_type": 1,
                "stats": [
                  {
                    "views": 2017,
                    "clicks": 27,
                    "atbs": 1,
                    "ctr": 1.34
                  }
                ]
              }
            ]
          }
        ],
        "expenses": 175000,
        "cr1": 1.91,
        "cr2": 25
      }
    ]
  }
]
```

> **Other response wrappers:**
> - `RespStatMediaDates`: wraps with `"dates": [...]` instead of `"interval": {...}`
> - `RespStatMediaWithoutParam`: no wrapper, just `"stats": [...]`
> - `RespStatMediaAggregate`: array mixing interval and dates entries
>
> All share identical `stats[]` item schema as shown above.

##### 400

- Content type: application/json

```json
{
  "error": "Incorrect request body"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Daily Search Clusters Statistics
`/adv/v1/normquery/stats`

- Method: `POST`
- URL: `https://advert-api.wildberries.ru/adv/v1/normquery/stats`

#### Method description
Returns statistics (views, clicks, add-to-cart, orders, CTR, CPC, CPM, etc.) by search clusters for the specified period detailed by day.

Request limit per one seller's account:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 1 min | 10 requests | 6 s | 20 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "from": "2026-01-01",
  "to": "2026-01-30",
  "items": [
    {
      "advertId": 123456789,
      "nmId": 987654321
    }
  ]
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `from` (required) | string \<date\> | Period start date |
| `to` (required) | string \<date\> | Period end date |
| `items` (required) | Array of objects \<= 100 items \<CampaignItem\> | |

##### CampaignItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `advertId` (required) | integer \<int64\> | Campaign ID |
| `nmId` (required) | integer \<int64\> | WB article |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "items": [
    {
      "advertId": 123456789,
      "dailyStats": [
        {
          "date": "2026-01-27",
          "stat": {
            "atbs": 39,
            "avgPos": 3.3,
            "clicks": 75,
            "cpc": 1.44,
            "cpm": 562.5,
            "ctr": 39.06,
            "normQuery": "Поисковый кластер 0",
            "orders": 9,
            "shks": 5,
            "spend": 108,
            "views": 192
          }
        },
        {
          "date": "2026-01-27",
          "stat": {
            "atbs": 71,
            "avgPos": 7.9,
            "clicks": 56,
            "cpc": 4.38,
            "cpm": 1290.95,
            "ctr": 29.47,
            "normQuery": "румяна для лица vivienne sabo",
            "orders": 2,
            "shks": 44,
            "spend": 245.28,
            "views": 190
          }
        }
      ],
      "nmId": 987654321
    }
  ]
}
```

> Note: One `dailyStats` entry per search cluster per day. Array truncated for brevity.

##### 400

- Content type: application/json

```json
{
  "detail": "incorrect request body, please check API documentation",
  "origin": "camp-api-public-cache",
  "request_id": "33e7d9f3fc221648cdf096bf8e62e482",
  "status": 400,
  "title": "invalid request body"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


## Promotions Calendar

> To access the methods, use a token for the Prices and Discounts category

Using these methods, you can obtain information about promotions and participate in them.

### Promotions List
`/api/v1/calendar/promotions`

- Method: `GET`
- URL: `https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions`

#### Method description
Returns a promotions list with dates and times of occurrence

Request limit per one seller's account for all methods in the Promotions Calendar category:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 6 s | 10 requests | 600 ms | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `startDateTime` (required) | string \<date-time\> | Example: `startDateTime=2023-09-01T00:00:00Z`<br>Period start, format `YYYY-MM-DDTHH:MM:SSZ` |
| `endDateTime` (required) | string \<date-time\> | Example: `endDateTime=2024-08-01T23:59:59Z`<br>Period end, format `YYYY-MM-DDTHH:MM:SSZ` |
| `allPromo` (required) | boolean | Default: `false`<br>Show promotions:<br>- `false` — available for participating<br>- `true` — all promotion |
| `limit` | integer \<uint\> \[ 1 .. 1000 \] | Example: `limit=10`<br>Number of requested promotions |
| `offset` | integer \<uint\> `>= 0` | Example: `offset=0`<br>From which element to start outputting data |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **402** | Payment Required |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "data": {
    "promotions": [
      {
        "id": 123,
        "name": "скидки",
        "startDateTime": "2023-06-05T21:00:00Z",
        "endDateTime": "2023-06-05T21:00:00Z",
        "type": "regular"
      }
    ]
  }
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `data` | object | Response data |
| `data.promotions` | Array of objects \<PromotionItem\> | Promotions list |
| `data.promotions[].id` | integer | Promotion ID |
| `data.promotions[].name` | string | Promotion name |
| `data.promotions[].startDateTime` | string \<date-time\> | Promotion start |
| `data.promotions[].endDateTime` | string \<date-time\> | Promotion end |
| `data.promotions[].type` | string | Enum: `"regular"` `"auto"`<br>Promotion type:<br>- `regular` — promotion<br>- `auto` — auto promotion |

##### 400

- Content type: application/json

```json
{
  "errorText": "Failed to parse data"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 402

- Content type: application/problem+json

```json
{
  "title": "payment required",
  "detail": "please top up your balance in your company personal account https://dev.wildberries.ru/company"
}
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)



### Promotions Details
`/api/v1/calendar/promotions/details`

- Method: `GET`
- URL: `https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions/details`

#### Method description
Returns detailed information about the selected promotions

Request limit per one seller's account for all methods in the Promotions Calendar category:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 6 s | 10 requests | 600 ms | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `promotionIDs` (required) | Array of integers \[ 1 .. 100 \] items unique | Example: `promotionIDs=1&promotionIDs=3&promotionIDs=64`<br>IDs of the promotions for which information should be returned |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **402** | Payment Required |
| **429** | Too Many Requests |


#### Response samples

##### 200

- Content type: application/json

```json
{
  "data": {
    "promotions": [
      {
        "id": 123,
        "name": "ХИТЫ ГОДА",
        "description": "В акции принимают участие самые популярные товары 2023 года. Карточки товаров будут выделены плашкой «ХИТ ГОДА», чтобы покупатели замечали эти товары среди других. Также они будут размещены под баннерами на главной странице и примут участие в PUSH-уведомлениях. С ценами для вступления в акцию вы можете ознакомиться ниже.",
        "advantages": [
          "Плашка",
          "Баннер",
          "Топ выдачи товаров"
        ],
        "startDateTime": "2023-06-05T21:00:00Z",
        "endDateTime": "2023-06-05T21:00:00Z",
        "inPromoActionLeftovers": 45,
        "inPromoActionTotal": 123,
        "notInPromoActionLeftovers": 3,
        "notInPromoActionTotal": 10,
        "participationPercentage": 10,
        "type": "auto",
        "exceptionProductsCount": 10,
        "ranging": [
          {
            "condition": "productsInPromotion",
            "participationRate": 10,
            "boost": 7
          },
          {
            "condition": "calculateProducts",
            "participationRate": 20,
            "boost": 17
          },
          {
            "condition": "allProducts",
            "participationRate": 35,
            "boost": 30
          }
        ]
      }
    ]
  }
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `data` | object | Response data |
| `data.promotions` | Array of objects \<PromotionDetailsItem\> | Promotions list |

##### PromotionDetailsItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `id` | integer | Promotion ID |
| `name` | string | Promotion name |
| `description` | string | Promotion description |
| `advantages` | Array of strings | Promotion advantages |
| `startDateTime` | string | Promotion start |
| `endDateTime` | string | Promotion end |
| `inPromoActionLeftovers` | integer | Number of products with remaining stock participating in the promotion |
| `inPromoActionTotal` | integer | Total number of products participating in the promotion |
| `notInPromoActionLeftovers` | integer | Number of products with remaining stock that are not participating in the promotion |
| `notInPromoActionTotal` | integer | Total number of products that are not participating in the promotion |
| `participationPercentage` | integer | Products already participating in the promotion, %. Calculation based on the products participating in the promotion and with the remaining stock |
| `type` | string | Enum: `"regular"` `"auto"`<br>Promotion type:<br>- `regular` — promotion<br>- `auto` — auto promotion |
| `exceptionProductsCount` | integer \<uint\> | Number of products excluded from the auto promotion before it starts. Only for `"type": "auto"`.<br>At the start of the promotion, these products will automatically be without a discount |
| `ranging` | Array of objects \<RangingItem\> | Ranking (if enabled) |

##### RangingItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `condition` | string | Type of ranking:<br>- `productsInPromotion` — only the seller's products participating in the promotion will be boosted<br>- `calculateProducts` — any of the seller's products proposed for participation in the promotion will be boosted<br>- `allProducts` — all of the seller's products will be boosted |
| `participationRate` | integer \<uint\> \[ 0 .. 100 \] | Percentage of seller's products needed to advance to the next ranking level, % |
| `boost` | integer \<uint\> | Current search boost level, % |

##### 400

- Content type: application/json

```json
{
  "errorText": "Failed to parse data"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 402

- Content type: application/json

```json
{
  "title": "payment required",
  "detail": "please top up your balance in your company personal account https://dev.wildberries.ru/company"
}
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### List of Products for Participating in the Promotion
`/api/v1/calendar/promotions/nomenclatures`

- Method: `GET`
- URL: `https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions/nomenclatures`

#### Method description
Returns a list of products suitable for participation in the promotion.

Not applicable for auto promotions

Request limit per one seller's account for all methods in the Promotions Calendar category:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 6 s | 10 requests | 600 ms | 5 requests |


#### Authorizations:

Header parameter name: `Authorization`

#### `query` Parameters

| Param | Type | Description |
| ----- | ---- | ----------- |
| `promotionID` (required) | integer | Example: `promotionID=1`<br>Promotion ID |
| `inAction` (required) | boolean | Default: `false`<br>Example: `inAction=true`<br>Participates in the promotion:<br>- `true` — yes<br>- `false` — no |
| `limit` | integer \<uint\> \[ 1 .. 1000 \] | Example: `limit=10`<br>Number of requested products |
| `offset` | integer \<uint\> `>= 0` | Example: `offset=0`<br>From which element to start outputting data |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **402** | Payment Required |
| **422** | Error processing request parameters |
| **429** | Too Many Requests |

#### Response samples

##### 200

- Content type: application/json

```json
{
  "data": {
    "nomenclatures": [
      {
        "id": 162579635,
        "inAction": true,
        "price": 1500,
        "currencyCode": "RUB",
        "planPrice": 1000,
        "discount": 15,
        "planDiscount": 34
      }
    ]
  }
}
```

##### 400

- Content type: application/json

```json
{
  "errorText": "Invalid query params"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 402

- Content type: application/json

```json
{
  "title": "payment required",
  "detail": "please top up your balance in your company personal account https://dev.wildberries.ru/company"
}
```

##### 422

- Content type: application/json

```json
{
  "errorText": "Unprocessable entity"
}
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)


### Add Product to the Promotion
`/api/v1/calendar/promotions/upload`

- Method: `POST`
- URL: `https://dp-calendar-api.wildberries.ru/api/v1/calendar/promotions/upload`

#### Method description
Creates a product upload for the promotion.
The upload status can be checked using separate methods.

Not applicable for auto promotions

Request limit per one seller's account for all methods in the Promotions Calendar category:

| Period | Limit | Interval | Burst |
|--------|-------|----------|-------|
| 6 s | 10 requests | 600 ms | 5 requests |

#### Authorizations:

Header parameter name: `Authorization`

#### Request Body schema (required): `application/json`

```json
{
  "data": {
    "promotionID": 1,
    "uploadNow": true,
    "nomenclatures": [
      75632091,
      31322455,
      642080796
    ]
  }
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `data` | object \<PromoItem\> | Request data |

##### PromoItem

| Param | Type | Description |
| ----- | ---- | ----------- |
| `promotionID` | integer `>= 1` | Promotion ID |
| `uploadNow` | boolean | Set discount:<br>- `true` — now<br>- `false` — at the start of the promotion |
| `nomenclatures` | Array of integers \[ 1 .. 1000 \] items unique \[ items `>= 1` \] | WB articles that can be added to the promotion |

#### Responses

| Code | Status |
| --- | --- |
| **200** | Success |
| **400** | Bad Request |
| **401** | Unauthorized |
| **402** | Payment Required |
| **422** | Error processing request parameters |
| **429** | Too Many Requests |

#### Request samples

> Note: this section is labeled "Request samples" in the original API docs but contains the **response** body for status 200.

##### 200

- Content type: application/json

```json
{
  "data": {
    "alreadyExists": false,
    "uploadID": 11
  }
}
```

| Param | Type | Description |
| ----- | ---- | ----------- |
| `data` | object \<DataUpload\> | Response data |

##### DataUpload

| Param | Type | Description |
| ----- | ---- | ----------- |
| `alreadyExists` | boolean | Upload with this data already exists |
| `uploadID` | integer | Upload ID |

##### 400

- Content type: application/json

```json
{
  "errorText": "Invalid query params"
}
```

##### 401
→ See [Unauthorized (401)](#unauthorized-401)

##### 402

- Content type: application/json

```json
{
  "title": "payment required",
  "detail": "please top up your balance in your company personal account https://dev.wildberries.ru/company"
}
```

##### 422

- Content type: application/json

```json
{
  "errorText": "Unprocessable entity"
}
```

##### 429
→ See [Too Many Requests (429)](#too-many-requests-429)
