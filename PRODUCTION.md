# Productionizing UCLA Dining API on AWS

This guide covers deploying and operating the UCLA Dining & Recreation scraper (`scraper.py`) and REST API (`ucla-dining-api`) on AWS.

---

## Architecture Overview

1. **Daily Scraper (`scraper.py` via Lambda + EventBridge Scheduler)**: Runs once daily at `00:05 America/Los_Angeles` via `lambda_handler` to scrape dining hours, dynamic hall menus & nutrition facts, food truck schedules, and gym hours/locations, writing gzip-compressed `dining-data.json` to S3.
2. **Storage (Amazon S3)**: Single gzipped JSON object `s3://<S3_BUCKET_NAME>/dining-data.json` (`ContentEncoding: gzip`, `ContentType: application/json`).
3. **REST API (`ucla-dining-api/`)**: FastAPI + Mangum deployed to AWS Lambda behind API Gateway via the Serverless Framework (`us-west-2`, Python 3.12).
4. **Caching**:
   - **In-memory Lambda cache (`S3Service`)**: Caches `dining-data.json` until midnight `America/Los_Angeles`, avoiding all S3 reads (`GetObject` and `HeadObject`) on warm invocations for the rest of the day. After midnight PT, it checks `HeadObject` and refreshes once the new day's file is uploaded.
   - **HTTP `Cache-Control`**: Menu, hall, item, truck, and gym endpoints emit `Cache-Control: public, max-age=<seconds_until_midnight_PT>`. Real-time `/activity` endpoints emit `Cache-Control: public, max-age=60`.
   - **Optional CloudFront**: Placing CloudFront in front of API Gateway honors `Cache-Control` at the edge for near-zero Lambda/S3 cost (cheaper than API Gateway's dedicated stage cache).

---

## Prerequisites

- AWS account + IAM credentials configured (`aws configure`)
- AWS CLI v2
- Python 3.12+
- Node.js 18+ and Serverless Framework (`npm install -g serverless`)
- Docker (builds Linux wheels for `lxml` on Lambda Python 3.12)

Set common shell variables for the commands below:

```bash
export AWS_REGION="us-west-2"
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export S3_BUCKET_NAME="u-c-lotta-adipose"
export S3_DATA_KEY="dining-data.json"
export STAGE="prod"
export SCRAPER_FUNCTION_NAME="ucla-dining-scraper"
```

---

## Step 1: Create the S3 Bucket & Bootstrap `dining-data.json`

Create the S3 bucket (skip if it already exists) and block public access:

```bash
aws s3api create-bucket \
  --bucket "$S3_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"

aws s3api put-public-access-block \
  --bucket "$S3_BUCKET_NAME" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

Run the first scrape locally to bootstrap `dining-data.json` (gzipped) in S3. A cold first run fetches every uncached menu item and takes a few minutes; subsequent daily runs in Lambda load `dining-data.json` from S3 first, skip already-cached items, and finish much faster (well under Lambda's 15-minute limit).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 -c "
from scraper import UCLADiningScraper
scraper = UCLADiningScraper()
ok = scraper.update_and_save(
    use_s3=True,
    bucket_name='$S3_BUCKET_NAME',
    dining_filename='$S3_DATA_KEY',
)
assert ok, 'Initial scrape/upload failed'
print('Bootstrapped s3://$S3_BUCKET_NAME/$S3_DATA_KEY')
"
```

Verify the object exists in S3:

```bash
aws s3 ls "s3://$S3_BUCKET_NAME/$S3_DATA_KEY"
```

---

## Step 2: Deploy the API (Lambda + API Gateway)

Install the Serverless plugin and deploy from `ucla-dining-api/`:

```bash
cd ucla-dining-api
npm init -y   # only if package.json does not exist yet
npm install --save-dev serverless-python-requirements

S3_BUCKET_NAME="$S3_BUCKET_NAME" serverless deploy --stage "$STAGE" --region "$AWS_REGION"
cd ..
```

Note the `endpoints:` URL printed at the end of `serverless deploy` (e.g. `https://<api-id>.execute-api.us-west-2.amazonaws.com/prod`) and export it:

```bash
export API_BASE_URL="https://<api-id>.execute-api.us-west-2.amazonaws.com/$STAGE"
```

To inspect logs or tear down later:

```bash
cd ucla-dining-api && serverless logs -f api --stage "$STAGE" --tail
# Teardown (when pausing AWS usage):
# S3_BUCKET_NAME="$S3_BUCKET_NAME" serverless remove --stage "$STAGE" --region "$AWS_REGION"
```

---

## Step 3: Schedule the Daily Scraper

### Option A: AWS Lambda + EventBridge Scheduler (~$0.00/mo, Recommended)

`scraper.py` includes `lambda_handler(event, context)` and uses `America/Los_Angeles` for all date/weekday calculations, so it runs safely on UTC Lambda.

#### 1. Create the Scraper Lambda IAM Role

```bash
cat << 'EOF' > /tmp/lambda-trust.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name "${SCRAPER_FUNCTION_NAME}-role" \
  --assume-role-policy-document file:///tmp/lambda-trust.json

aws iam attach-role-policy \
  --role-name "${SCRAPER_FUNCTION_NAME}-role" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

cat << EOF > /tmp/scraper-s3-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::${S3_BUCKET_NAME}/${S3_DATA_KEY}"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name "${SCRAPER_FUNCTION_NAME}-role" \
  --policy-name "S3DiningDataAccess" \
  --policy-document file:///tmp/scraper-s3-policy.json
```

*(If you enable API Gateway stage caching, also grant `apigateway:DELETE` on `arn:aws:apigateway:us-west-2::/restapis/<api-id>/stages/prod/cache/data` and add `API_GATEWAY_REST_API_ID` / `API_GATEWAY_STAGE_NAME` to the Lambda environment.)*

#### 2. Package & Deploy the Scraper Lambda (with Docker for `lxml`)

Build a lean deployment zip containing only `scraper.py` + `beautifulsoup4`, `lxml`, and `requests` (`boto3` is preinstalled in the Lambda Python 3.12 runtime):

```bash
rm -rf /tmp/scraper-pkg /tmp/scraper-lambda.zip
mkdir -p /tmp/scraper-pkg
cp scraper.py /tmp/scraper-pkg/

docker run --rm -v /tmp/scraper-pkg:/var/task \
  public.ecr.aws/sam/build-python3.12 \
  pip install beautifulsoup4==4.13.4 lxml==5.4.0 requests==2.32.3 -t /var/task

(cd /tmp/scraper-pkg && zip -r9 /tmp/scraper-lambda.zip .)

aws lambda create-function \
  --function-name "$SCRAPER_FUNCTION_NAME" \
  --runtime python3.12 \
  --role "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${SCRAPER_FUNCTION_NAME}-role" \
  --handler scraper.lambda_handler \
  --zip-file fileb:///tmp/scraper-lambda.zip \
  --timeout 900 \
  --memory-size 512 \
  --environment "Variables={S3_BUCKET_NAME=${S3_BUCKET_NAME},S3_DATA_KEY=${S3_DATA_KEY}}" \
  --region "$AWS_REGION"
```

*(To update `scraper.py` later, rebuild `/tmp/scraper-lambda.zip` and run `aws lambda update-function-code --function-name "$SCRAPER_FUNCTION_NAME" --zip-file fileb:///tmp/scraper-lambda.zip --region "$AWS_REGION"`.)*

Test invoking the scraper Lambda once manually:

```bash
aws lambda invoke \
  --function-name "$SCRAPER_FUNCTION_NAME" \
  --region "$AWS_REGION" \
  /tmp/scraper-out.json && cat /tmp/scraper-out.json
```

#### 3. Schedule Daily Execution at 12:05 AM PT via EventBridge Scheduler

Create the execution role for EventBridge Scheduler and attach the daily schedule (`America/Los_Angeles` handles PST/PDT transitions automatically):

```bash
cat << 'EOF' > /tmp/scheduler-trust.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "scheduler.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name "${SCRAPER_FUNCTION_NAME}-scheduler-role" \
  --assume-role-policy-document file:///tmp/scheduler-trust.json

cat << EOF > /tmp/scheduler-invoke-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${SCRAPER_FUNCTION_NAME}"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name "${SCRAPER_FUNCTION_NAME}-scheduler-role" \
  --policy-name "InvokeScraperLambda" \
  --policy-document file:///tmp/scheduler-invoke-policy.json

aws scheduler create-schedule \
  --name "${SCRAPER_FUNCTION_NAME}-daily" \
  --schedule-expression "cron(5 0 * * ? *)" \
  --schedule-expression-timezone "America/Los_Angeles" \
  --flexible-time-window '{"Mode":"OFF"}' \
  --target "{
    \"Arn\": \"arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${SCRAPER_FUNCTION_NAME}\",
    \"RoleArn\": \"arn:aws:iam::${AWS_ACCOUNT_ID}:role/${SCRAPER_FUNCTION_NAME}-scheduler-role\"
  }" \
  --region "$AWS_REGION"
```

---

### Option B: EC2 Instance + Cron (Persistent Host Alternative)

If you prefer a dedicated EC2 host (`t4g.nano` / `t3.micro` in `us-west-2`):

1. Attach an IAM Instance Profile with `s3:GetObject` and `s3:PutObject` on `arn:aws:s3:::u-c-lotta-adipose/dining-data.json`.
2. Clone the repo and install dependencies (`python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`).
3. Create `~/run_scraper.sh`:

```bash
cat << 'EOF' > ~/run_scraper.sh
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/u-c-lotta-adipose
source .venv/bin/activate
python3 -c "
from scraper import UCLADiningScraper
scraper = UCLADiningScraper()
ok = scraper.update_and_save(use_s3=True, bucket_name='u-c-lotta-adipose', dining_filename='dining-data.json')
if not ok:
    raise SystemExit(1)
"
EOF
chmod +x ~/run_scraper.sh
```

4. Schedule via `crontab -e`:

```cron
CRON_TZ=America/Los_Angeles
5 0 * * * /home/ubuntu/run_scraper.sh >> /home/ubuntu/scraper.log 2>&1
```

---

## Step 4: Optional CloudFront Edge Caching

Because the API already sets `Cache-Control: public, max-age=<seconds_until_midnight_PT>` on menu/hall/item/truck/gym routes and `max-age=60` on `/activity`:

1. Create a CloudFront distribution with your API Gateway invoke URL as the origin (origin path `/prod`).
2. Use the managed **`CachingOptimized`** cache policy (or a custom policy that forwards query strings `date`, `meal`, `day`, `open`, `q`, `dietary`, `allergen`, `items` and respects origin `Cache-Control` headers).
3. This serves repeated requests from CloudFront's edge cache without invoking Lambda or S3 at all.

---

## Step 5: Smoke-Test Production Endpoints

Run these checks against `$API_BASE_URL` after deployment:

```bash
# Health check
curl -s "$API_BASE_URL/health" | jq

# Dining halls & dynamic menus
curl -s "$API_BASE_URL/halls" | jq '.halls | length'
curl -s "$API_BASE_URL/halls/b-plate/hours?day=wed" | jq
curl -s "$API_BASE_URL/halls/cafe-1919/menu?meal=all_day" | jq

# Verify EOD Cache-Control header on menu endpoints
curl -sI "$API_BASE_URL/halls/b-plate" | grep -i cache-control

# Food trucks
curl -s "$API_BASE_URL/trucks" | jq

# Gyms (hours, special hours, locations)
curl -s "$API_BASE_URL/gyms" | jq
curl -s "$API_BASE_URL/gyms/wooden/hours?day=mon" | jq

# Live activity levels (11 dining halls + 3 gyms) & 60s Cache-Control
curl -s "$API_BASE_URL/activity" | jq
curl -sI "$API_BASE_URL/activity/b-plate" | grep -i cache-control

# Item lookup, search, and multi-item nutrition calculation
curl -s "$API_BASE_URL/search?q=chicken" | jq '.count'
curl -s "$API_BASE_URL/nutrition/calculate?items=4318:1,2201:2" | jq '.nutrition.calories'
```

---

## Step 6: CloudWatch Logging, Metrics & Alarms

### 1. Lambda Log Retention & Inspection (API + Scraper)

Both Lambdas automatically log to CloudWatch. Set a 14-day retention policy on both log groups so you don't pay for indefinite log storage:

```bash
export API_LOG_GROUP="/aws/lambda/ucla-dining-api-$STAGE-api"
export SCRAPER_LOG_GROUP="/aws/lambda/$SCRAPER_FUNCTION_NAME"

aws logs put-retention-policy \
  --log-group-name "$API_LOG_GROUP" \
  --retention-in-days 14 \
  --region "$AWS_REGION"

aws logs create-log-group \
  --log-group-name "$SCRAPER_LOG_GROUP" \
  --region "$AWS_REGION" 2>/dev/null || true

aws logs put-retention-policy \
  --log-group-name "$SCRAPER_LOG_GROUP" \
  --retention-in-days 14 \
  --region "$AWS_REGION"
```

Useful log queries:

```bash
# Tail API or scraper logs live
aws logs tail "$API_LOG_GROUP" --follow --region "$AWS_REGION"
aws logs tail "$SCRAPER_LOG_GROUP" --follow --region "$AWS_REGION"

# Check API errors over the last 24h
aws logs filter-log-events \
  --log-group-name "$API_LOG_GROUP" \
  --filter-pattern "ERROR" \
  --start-time $(( ($(date +%s) - 86400) * 1000 )) \
  --region "$AWS_REGION"

# Verify EOD cache behavior (count actual S3 fetches vs in-memory cache hits)
aws logs filter-log-events \
  --log-group-name "$API_LOG_GROUP" \
  --filter-pattern '"Fetching dining data from S3"' \
  --start-time $(( ($(date +%s) - 86400) * 1000 )) \
  --region "$AWS_REGION"
```

### 2. CloudWatch Alarms & SNS Email Alerts

Create an SNS topic and subscribe your email (confirm the subscription email AWS sends):

```bash
export ALERT_EMAIL="you@example.com"
export SNS_TOPIC_ARN=$(aws sns create-topic \
  --name ucla-dining-alerts \
  --region "$AWS_REGION" \
  --query 'TopicArn' --output text)

aws sns subscribe \
  --topic-arn "$SNS_TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "$ALERT_EMAIL" \
  --region "$AWS_REGION"
```

Create alarms for **API Lambda errors**, **API Gateway 5XX errors**, and **Scraper Lambda errors**:

```bash
# 1. API Lambda function errors (> 0 in 5 minutes)
aws cloudwatch put-metric-alarm \
  --alarm-name "ucla-dining-api-lambda-errors" \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value="ucla-dining-api-$STAGE-api" \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region "$AWS_REGION"

# 2. API Gateway 5XX errors (> 0 in 5 minutes)
aws cloudwatch put-metric-alarm \
  --alarm-name "ucla-dining-api-5xx" \
  --namespace AWS/ApiGateway \
  --metric-name 5XXError \
  --dimensions Name=ApiName,Value="$STAGE-ucla-dining-api" Name=Stage,Value="$STAGE" \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region "$AWS_REGION"

# 3. Scraper Lambda errors (> 0 in 1 hour; fires if lambda_handler raises or times out)
aws cloudwatch put-metric-alarm \
  --alarm-name "ucla-dining-scraper-errors" \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value="$SCRAPER_FUNCTION_NAME" \
  --statistic Sum \
  --period 3600 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "$SNS_TOPIC_ARN" \
  --region "$AWS_REGION"
```

*(If using Option B / EC2 instead of Lambda, install `amazon-cloudwatch-agent` to ship `/home/ubuntu/scraper.log` to a custom log group and attach a `logs put-metric-filter` for `"ERROR"`.)*

---

## Troubleshooting

- **Stale data after midnight PT**: The API Lambda cache expires at `00:00:00 America/Los_Angeles`. Since the scraper runs at `00:05`, any API request between `00:00` and `00:05` extends the previous day's cache for 5 minutes (`STALE_RETRY_SECONDS = 300`), after which the next request detects the new S3 `LastModified` timestamp and refreshes automatically.
- **Cold-run scraper timeout in Lambda**: Always run Step 1 locally first to populate `items` in S3. If you ever wipe `dining-data.json` and want Lambda to rebuild from scratch without hitting the 15-minute timeout, run Step 1 locally again.
- **`403 AccessDenied` on S3**: Verify `S3_BUCKET_NAME` matches the bucket in `serverless.yml` and both Lambda roles have the required S3 permissions (`GetObject`/`HeadObject` for the API role; `GetObject`/`PutObject` for the scraper role).
- **Docker build issues with `lxml`**: Ensure Docker is running locally before packaging either Lambda (`serverless deploy` or `docker run ... sam/build-python3.12`), so Linux C-extension wheels are built for Python 3.12.
