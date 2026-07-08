# Phase 1 Setup Guide — Immediate Kill Switch

`AWS Budgets → SNS → Lambda (Heavy Hitter)`

Lambda fires FIRST the moment your budget is breached. This is your primary line of defense.

---

## Prerequisites

- [ ] Your own AWS account with root or admin access
- [ ] Your AWS Account ID (12-digit number — top-right dropdown in Console)
- [ ] Python 3.x installed locally (for optional local testing)

---

## Step 1: Create the SNS Topic (The Alarm Bell)

> [!NOTE]
> Create the SNS topic in **ap-south-1 (Mumbai)** since that's your primary region.

### Console Method
1. **Switch region** to **Asia Pacific (Mumbai) ap-south-1** in the top-right
2. Go to **Amazon SNS** → **Topics** → **Create topic**
3. Type: **Standard** (NOT FIFO)
4. Name: `Budget-Kill-Switch-Topic`
5. Leave all other settings as default
6. Click **Create topic**
7. **📋 Copy the Topic ARN** — you'll need it everywhere
   - It looks like: `arn:aws:sns:ap-south-1:123456789012:Budget-Kill-Switch-Topic`

### CLI Alternative
```powershell
aws sns create-topic --name Budget-Kill-Switch-Topic --region ap-south-1
```

### (Optional) Subscribe Your Email for Notifications
1. On the topic page, click **Create subscription**
2. Protocol: **Email**
3. Endpoint: **your-email@gmail.com**
4. Click **Create subscription**
5. **Check your email** and click the confirmation link!

---

## Step 2: Create the Lambda Execution Role (Permissions)

### Console Method
1. Go to **IAM** → **Roles** → **Create role**
   - (IAM is global, no region needed)
2. Trusted entity type: **AWS service**
3. Use case: **Lambda**
4. Click **Next**

#### Attach the Built-in Policy
5. Search for and check: `AWSLambdaBasicExecutionRole`
6. Click **Next**

7. Role name: `Lambda-Kill-Switch-Role`
8. Click **Create role**

#### Attach the Custom Policy
9. Click on the newly created `Lambda-Kill-Switch-Role`
10. Go to the **Permissions** tab → **Add permissions** → **Create inline policy**
11. Click the **JSON** tab
12. Paste the contents of `iam/lambda-permissions-policy.json` from this project
13. Name it: `KillSwitchResourceTermination`
14. Click **Create policy**

### CLI Alternative
```powershell
# Create the role
aws iam create-role `
  --role-name Lambda-Kill-Switch-Role `
  --assume-role-policy-document file://iam/lambda-execution-role.json

# Attach the basic Lambda execution policy
aws iam attach-role-policy `
  --role-name Lambda-Kill-Switch-Role `
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Attach the custom termination policy
aws iam put-role-policy `
  --role-name Lambda-Kill-Switch-Role `
  --policy-name KillSwitchResourceTermination `
  --policy-document file://iam/lambda-permissions-policy.json
```

---

## Step 3: Create the Lambda Function (The Executioner)

> [!IMPORTANT]
> Create the Lambda in **ap-south-1 (Mumbai)** — the same region as your SNS topic.

### Console Method
1. **Switch region** to **ap-south-1 (Mumbai)**
2. Go to **AWS Lambda** → **Create function**
3. Choose: **Author from scratch**
4. Function name: `Nuclear-Button`
5. Runtime: **Python 3.12** (or latest 3.x)
6. Architecture: **x86_64**
7. Expand **"Change default execution role"**:
   - Select **Use an existing role**
   - Choose: `Lambda-Kill-Switch-Role`
8. Click **Create function**

#### Upload the Code
9. Scroll down to the **Code source** section
10. Open `lambda/heavy_hitter.py` from this project
11. Replace all the code in `lambda_function.py` with the contents of `heavy_hitter.py`

> [!IMPORTANT]
> **Rename the file!** In the Lambda console editor, rename `lambda_function.py` to `heavy_hitter.py` — OR change the Handler setting (step 12a below) to match.

12. Click **Deploy**

#### Configure Settings
13. Go to **Configuration** → **General configuration** → **Edit**
    - Set **Handler** to: `heavy_hitter.lambda_handler`
14. Set **Timeout** to: `5 minutes` (300 seconds)
    - The script scans Mumbai first, then all other regions
15. Set **Memory** to: `256 MB`
16. Click **Save**

#### Wire Up the SNS Trigger
17. In the Lambda **Function overview**, click **+ Add trigger**
18. Select: **SNS**
19. SNS topic: Select `Budget-Kill-Switch-Topic`
20. Click **Add**

### CLI Alternative
```powershell
# Zip the Lambda code
cd lambda
Compress-Archive -Path heavy_hitter.py -DestinationPath lambda_deployment_package.zip

# Create the function (replace YOUR_ACCOUNT_ID)
aws lambda create-function `
  --function-name Nuclear-Button `
  --runtime python3.12 `
  --handler heavy_hitter.lambda_handler `
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/Lambda-Kill-Switch-Role `
  --zip-file fileb://lambda_deployment_package.zip `
  --timeout 300 `
  --memory-size 256 `
  --region ap-south-1

# Allow SNS to invoke Lambda
aws lambda add-permission `
  --function-name Nuclear-Button `
  --statement-id sns-trigger `
  --action lambda:InvokeFunction `
  --principal sns.amazonaws.com `
  --source-arn arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:Budget-Kill-Switch-Topic `
  --region ap-south-1

# Subscribe Lambda to SNS
aws sns subscribe `
  --topic-arn arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:Budget-Kill-Switch-Topic `
  --protocol lambda `
  --notification-endpoint arn:aws:lambda:ap-south-1:YOUR_ACCOUNT_ID:function:Nuclear-Button `
  --region ap-south-1
```

---

## Step 4: Create the Budget (The Watchdog)

> [!NOTE]
> AWS Budgets is a **global** service — it monitors spending across ALL regions automatically. You don't need to create separate budgets per region.

### Console Method
1. Go to **AWS Billing** → **Budgets** → **Create budget**
2. Choose: **Customize (Advanced)**
3. Budget type: **Cost budget**
4. Click **Next**

#### Set the Amount
5. Budget name: `Kill-Switch-Budget`
6. Period: **Monthly**
7. Budget amount: **Fixed** → `$0.01`
8. Click **Next**

#### Configure the Alert
9. Click **Add an alert threshold**
10. Threshold: `100` % of budgeted amount
11. Trigger: **Actual** (not Forecasted)
12. Notification preferences:
    - **✅ Check** "Amazon SNS Alerts"
    - Paste your SNS Topic ARN: `arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:Budget-Kill-Switch-Topic`
    - (Optional) Also add your email address for a personal notification
13. Click **Next** → **Create budget**

> [!WARNING]
> **SNS topic for Budgets must be in us-east-1!** AWS Budgets can only send to SNS topics in `us-east-1`. If this is the case, you have two options:
> - **Option A:** Create a second SNS topic in `us-east-1` just for Budgets, then set up a cross-region SNS subscription to forward to your Mumbai Lambda
> - **Option B:** Create your main SNS topic AND Lambda in `us-east-1`, but set the Lambda script's `PRIMARY_REGION` to `ap-south-1` (already done — the script scans Mumbai first regardless of where Lambda is deployed)
>
> **Option B is simpler.** If you hit this issue, just recreate the SNS topic and Lambda in `us-east-1`. The script already handles Mumbai-first scanning.

---

## Step 5: Verify the Wiring

| Check | How to Verify |
|-------|---------------|
| SNS Topic exists | SNS → Topics → `Budget-Kill-Switch-Topic` visible |
| Lambda function exists | Lambda → Functions → `Nuclear-Button` visible |
| Lambda has SNS trigger | Lambda → `Nuclear-Button` → Triggers shows SNS |
| Lambda has correct role | Lambda → Configuration → Permissions → `Lambda-Kill-Switch-Role` |
| Lambda timeout is 5 min | Lambda → Configuration → General → Timeout = 5:00 |
| Lambda handler is correct | Lambda → Configuration → General → `heavy_hitter.lambda_handler` |
| Budget exists | Billing → Budgets → `Kill-Switch-Budget` visible |
| Budget has SNS notification | Budget → Alert details → Shows SNS Topic ARN |

---

## What's Next?

✅ Phase 1 is complete! Head to **Testing Guide** (`setup-guides/testing-guide.md`) to safely test.

Once Phase 1 is working, proceed to **Phase 2 Setup** (`setup-guides/phase2-setup.md`) to add aws-nuke deep cleanup.
