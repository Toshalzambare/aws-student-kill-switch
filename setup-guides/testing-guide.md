# Testing Guide — Safe Testing Without Spending Money

This guide shows you how to test every component of the AWS Nuclear Button without triggering a real budget alert or spending a single cent.

> [!TIP]
> Think of it like a fire drill — you manually ring the alarm to make sure the sprinklers work, without actually setting anything on fire. 🔥

---

## Test Matrix

| Test | What You're Testing | Cost | Risk |
|------|-------------------|------|------|
| Test 1 | Lambda DRY-RUN (code logic) | $0.00 | None |
| Test 2 | Lambda LIVE (actual termination) | $0.00* | Low |
| Test 3 | SNS → Lambda wiring | $0.00 | None |
| Test 4 | Full Phase 1 flow (end-to-end) | $0.00* | Low |
| Test 5 | SQS → Local Worker | $0.00 | None |
| Test 6 | Full hybrid flow (Lambda + aws-nuke) | $0.00* | Low |

*Only if using a free-tier eligible EC2 instance

---

## Test 1: Lambda DRY-RUN (Verify the Code Works)

This tests your Lambda function's logic without deleting anything.

### Steps
1. Go to **AWS Lambda** → `Nuclear-Button` (make sure you're in **ap-south-1**)
2. Open the code editor
3. **Temporarily change** `DRY_RUN = False` to `DRY_RUN = True`
4. Click **Deploy**
5. Click **Test** → **Create new test event**
6. Event name: `TestBudgetAlert`
7. Paste this test payload (simulates an SNS message):

```json
{
  "Records": [
    {
      "EventSource": "aws:sns",
      "Sns": {
        "Type": "Notification",
        "Subject": "AWS Budget Notification",
        "Message": "AWS Budget Alert: Your budget Kill-Switch-Budget has exceeded $0.01. Current spend: $0.02."
      }
    }
  ]
}
```

8. Click **Test**

### Expected Result
- ✅ Status: **Succeeded**
- ✅ Logs show `[DRY-RUN]` messages for each region
- ✅ Logs show **ap-south-1 (Mumbai) is scanned FIRST** before other regions
- ✅ No resources are actually terminated

> [!IMPORTANT]
> **Remember to change `DRY_RUN` back to `False`** after this test!

---

## Test 2: Lambda LIVE (Actual Termination)

This tests that Lambda can actually terminate a running EC2 instance in Mumbai.

### Step 1: Launch a Dummy Target
1. **Switch region** to **ap-south-1 (Mumbai)**
2. Go to **EC2** → **Launch Instance**
3. Name: `kill-switch-test-target`
4. AMI: **Amazon Linux 2023** (Free Tier eligible)
5. Instance type: **t2.micro** (Free Tier — if your account is under 12 months)
6. Key pair: **Proceed without a key pair**
7. Click **Launch instance**
8. Wait until state shows **Running**

### Step 2: Trigger the Lambda
1. Go to **Lambda** → `Nuclear-Button`
2. Make sure `DRY_RUN = False`
3. Click **Test** with the same `TestBudgetAlert` event

### Step 3: Verify
1. Go to **EC2** → **Instances** (in ap-south-1)
2. ✅ Your `kill-switch-test-target` should show: **shutting-down** → **terminated**
3. Check **CloudWatch Logs** → `/aws/lambda/Nuclear-Button` for detailed output

### Step 4: Cleanup
Already done — the instance terminated itself! 🎉

---

## Test 3: SNS → Lambda Wiring (Manual Alarm)

This tests that publishing to the SNS topic correctly triggers Lambda.

### Steps
1. Set Lambda `DRY_RUN = True` (safe mode)
2. Go to **Amazon SNS** → **Topics** → `Budget-Kill-Switch-Topic` (in ap-south-1)
3. Click **Publish message**
4. Subject: `Test Budget Alert`
5. Message body:
```
Manual test of the kill switch pipeline. Not a real alert.
```
6. Click **Publish message**

### Verify
1. Go to **CloudWatch Logs** → `/aws/lambda/Nuclear-Button`
2. ✅ A new log stream appears within seconds
3. ✅ Logs show Lambda triggered and ran in DRY-RUN mode
4. ✅ If you subscribed your email, you also got an email!

---

## Test 4: Full Phase 1 Flow (End-to-End)

Combines Tests 2 and 3 — SNS publish that actually terminates an instance.

### Steps
1. Launch a `t2.micro` dummy target in Mumbai (same as Test 2)
2. Set Lambda `DRY_RUN = False`
3. Publish a message to the SNS topic (same as Test 3)
4. Watch the EC2 dashboard

### Expected Result
- ✅ Lambda triggers within seconds of the SNS publish
- ✅ Dummy EC2 instance goes **Running** → **Terminated**
- ✅ CloudWatch logs show Mumbai scanned first, then other regions
- ✅ Email notification received (if subscribed)

---

## Test 5: SQS → Local Worker (Phase 2)

> [!NOTE]
> Only proceed after completing Phase 2 setup.

### Steps
1. Start the local worker in dry-run mode:
```powershell
cd "c:\Users\zamba\OneDrive\Desktop\TEMP\Dump\AWS try\local-worker"
python sqs_worker.py --test --dry-run
```

2. In a separate terminal, send a test message to the SQS queue:
```powershell
aws sqs send-message `
  --queue-url https://sqs.ap-south-1.amazonaws.com/YOUR_ACCOUNT_ID/kill-switch-queue `
  --message-body "Test budget alert - manual trigger" `
  --region ap-south-1
```

### Expected Result
- ✅ The local worker picks up the message within seconds
- ✅ Logs show aws-nuke running in `--dry-run` mode
- ✅ Message is deleted from the queue after processing

---

## Test 6: Full Hybrid Flow (Lambda + aws-nuke)

The ultimate test — both Lambda AND the local worker fire.

### Path A: Laptop Online (Both Fire)
1. Start the local worker: `python sqs_worker.py --dry-run`
2. Publish a message to the SNS topic
3. ✅ Lambda fires **immediately** (check CloudWatch)
4. ✅ SQS message delivered, local worker picks it up and runs aws-nuke (dry-run)
5. ✅ Both systems activated simultaneously

### Path B: Laptop Offline (Lambda Only)
1. **Do NOT** start the local worker
2. Publish a message to the SNS topic
3. ✅ Lambda fires immediately (check CloudWatch)
4. ✅ SQS message sits in queue, expires after 24 hours
5. ✅ Your wallet is still protected — Lambda already killed everything expensive

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Lambda shows "Timeout" | Increase timeout to 5-10 min in Configuration |
| Lambda shows "Access Denied" | Check IAM role has all required policies |
| SNS doesn't trigger Lambda | Verify the subscription is **Confirmed** (not "Pending") |
| SQS not receiving messages | Check the SQS access policy allows SNS |
| aws-nuke says "account alias required" | Run: `aws iam create-account-alias --account-alias your-alias` |
| Local worker can't find aws-nuke | Update `AWS_NUKE_PATH` in sqs_worker.py |
| No CloudWatch logs | Verify `AWSLambdaBasicExecutionRole` is on the role |
| Budget can't send to SNS | AWS Budgets only supports SNS in `us-east-1` — see Phase 1 guide warning |

---

## Post-Testing Checklist

After all tests pass:

- [ ] Set Lambda `DRY_RUN = False` for production
- [ ] Verify no test EC2 instances are still running
- [ ] Verify the AWS Budget has the correct SNS ARN
- [ ] Start the local worker in live mode (if using Phase 2)
- [ ] (Optional) Set up local worker as a Windows Task Scheduler job

> [!CAUTION]
> **Final reminder:** AWS Budgets evaluates costs only ~3 times per day. There can be a delay of several hours between incurring a charge and the alert firing. The kill switch is a safety net, not instant protection. Always be mindful of what you launch!
