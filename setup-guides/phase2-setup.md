# Phase 2 Setup Guide — Deep Cleanup Layer (aws-nuke)

`SNS → SQS → Local Worker → aws-nuke`

This adds a secondary deep cleanup layer. By the time this runs, **Lambda has already fired** and killed the top 8 cost-generating services. aws-nuke is the thorough follow-up that catches everything else.

> [!NOTE]
> This phase is **optional but recommended**. Phase 1 alone protects you from the biggest bills. Phase 2 ensures absolutely nothing survives.

---

## Prerequisites

- [x] Phase 1 completed and tested
- [ ] Python 3.8+ installed on your local machine
- [ ] AWS CLI configured (`aws configure` — use ap-south-1 as default region)
- [ ] pip installed

---

## Step 1: Create the SQS Queue

Just one simple queue — no DLQ needed since Lambda already handled the critical stuff.

### Console Method
1. **Switch region** to **ap-south-1 (Mumbai)**
2. Go to **Amazon SQS** → **Create queue**
3. Type: **Standard**
4. Name: `kill-switch-queue`
5. Configuration:
   - **Visibility timeout**: `600` seconds (10 min — gives aws-nuke time to run)
   - **Message retention period**: `1 day` (24 hours — message expires if laptop never picks it up, no big deal since Lambda already ran)
   - **Delivery delay**: `0` seconds
6. Leave Dead-letter queue **disabled** — we don't need it
7. Click **Create queue**
8. **📋 Copy the Queue URL** (looks like `https://sqs.ap-south-1.amazonaws.com/123456789012/kill-switch-queue`)

### CLI Alternative
```powershell
aws sqs create-queue `
  --queue-name kill-switch-queue `
  --attributes "VisibilityTimeout=600,MessageRetentionPeriod=86400" `
  --region ap-south-1
```

---

## Step 2: Subscribe the SQS Queue to SNS

SNS will fan out the budget alert to **three subscribers simultaneously**:
1. ⚡ Lambda (immediate kill — already set up in Phase 1)
2. 📨 SQS Queue (for local aws-nuke — setting up now)
3. 📧 Email (notification — already set up in Phase 1)

### Console Method
1. Go to **Amazon SNS** → **Topics** → `Budget-Kill-Switch-Topic`
2. Click **Create subscription**
3. Protocol: **Amazon SQS**
4. Endpoint: Paste the **ARN** of `kill-switch-queue`
   - ARN looks like: `arn:aws:sqs:ap-south-1:YOUR_ACCOUNT_ID:kill-switch-queue`
5. Check **Enable raw message delivery** (optional but cleaner)
6. Click **Create subscription**

### Set SQS Access Policy (Allow SNS to Send Messages)
7. Go to **Amazon SQS** → `kill-switch-queue` → **Access policy** tab → **Edit**
8. Replace the policy with:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSNSPublish",
      "Effect": "Allow",
      "Principal": {
        "Service": "sns.amazonaws.com"
      },
      "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:ap-south-1:YOUR_ACCOUNT_ID:kill-switch-queue",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:Budget-Kill-Switch-Topic"
        }
      }
    }
  ]
}
```
9. Click **Save**

### CLI Alternative
```powershell
aws sns subscribe `
  --topic-arn arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:Budget-Kill-Switch-Topic `
  --protocol sqs `
  --notification-endpoint arn:aws:sqs:ap-south-1:YOUR_ACCOUNT_ID:kill-switch-queue `
  --region ap-south-1
```

---

## Step 3: Install aws-nuke on Your Local Machine

### Windows
1. Go to: https://github.com/rebuy-de/aws-nuke/releases
2. Download the latest `aws-nuke-*-windows-amd64.zip`
3. Extract and add to your PATH (or note the full path)

### Verify Installation
```powershell
aws-nuke version
```

### Set Your Account Alias (Required by aws-nuke)
aws-nuke **requires** an Account Alias as a safety check. Set it if you haven't:

```powershell
aws iam create-account-alias --account-alias your-chosen-alias
```

---

## Step 4: Configure aws-nuke

1. Open `local-worker/nuke-config.yaml`
2. Replace `YOUR_ACCOUNT_ID_HERE` with your actual 12-digit AWS Account ID
3. Review the filters section — the kill switch infrastructure is already protected

### Test aws-nuke in Dry-Run Mode First!
```powershell
aws-nuke -c local-worker/nuke-config.yaml --profile default
```
This shows everything it **would** delete without actually deleting anything (dry-run is the default).

---

## Step 5: Set Up the Local Worker

### Install Dependencies
```powershell
cd "c:\Users\zamba\OneDrive\Desktop\TEMP\Dump\AWS try\local-worker"
pip install -r requirements.txt
```

### Configure the Worker
1. Open `local-worker/sqs_worker.py`
2. Update these variables at the top:
   - `SQS_QUEUE_URL` → Your actual queue URL from Step 1
   - `AWS_NUKE_PATH` → Path to aws-nuke binary (if not on PATH)

### Start the Worker (Dry-Run First!)
```powershell
# Preview mode — see what would happen
python sqs_worker.py --dry-run

# Test mode — process one message and exit
python sqs_worker.py --test --dry-run
```

### Start the Worker (Live Mode)
```powershell
# ⚠️ ONLY after you've confirmed dry-run works!
python sqs_worker.py
```

---

## Step 6: (Optional) Run Worker as a Windows Background Service

### Windows — Task Scheduler
1. Open **Task Scheduler** → **Create Task**
2. Name: `AWS Kill Switch Worker`
3. Trigger: **At log on** (starts when you log into Windows)
4. Action: **Start a program**
   - Program: `python`
   - Arguments: `"c:\Users\zamba\OneDrive\Desktop\TEMP\Dump\AWS try\local-worker\sqs_worker.py"`
5. Check **"Run whether user is logged on or not"**

---

## Complete Flow After Phase 2

```
Budget breached ($0.01)
       │
       ▼
   SNS Topic ─────────────────────┬──────────────────┐
       │                          │                   │
       ▼                          ▼                   ▼
   ⚡ Lambda                 📨 SQS Queue        📧 Email
   (INSTANT)                     │               (Notification)
       │                         │
       ▼                    Laptop Online?
   Heavy Hitter kills       YES → aws-nuke runs
   top 8 services ✅              complete wipe ✅
                            NO  → Message expires
                                  in 24 hrs (fine,
                                  Lambda already
                                  handled it) ✅
```

---

## What's Next?

Head to **Testing Guide** (`setup-guides/testing-guide.md`) to safely test the full flow.
