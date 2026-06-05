# aiademo-bedrock-key-rotator

Lambda function that automatically rotates the short-term Bedrock bearer token used by the `voice-assistant` ECS service.

## Purpose

This Lambda rotates the Bedrock bearer token stored in AWS Secrets Manager.

The rotation flow is:

1. Generate a new Bedrock bearer token.
2. Validate the token with a Bedrock self-test.
3. Store the validated token as `AWSPENDING`.
4. Promote the validated token to `AWSCURRENT`.
5. Force a new ECS deployment so the container reloads the updated secret.

This prevents commercial/demo users from manually generating or pasting Bedrock tokens.

## AWS resources

- Secret: `aiademo/shared/bedrock-api-key`
- Lambda: `aiademo-bedrock-key-rotator`
- ECS cluster: `aiademo-cluster`
- ECS service: `aiademo-voice-assistant-service`
- Region: `eu-west-3`

## Rotation schedule

```text
rate(4 hours)
Duration: 1h
```

The Lambda currently generates a token with a 6-hour lifetime, so the 4-hour schedule provides a safety margin.

## Useful checks

Check rotation status:

```powershell
$SecretArn = "arn:aws:secretsmanager:eu-west-3:442042532301:secret:aiademo/shared/bedrock-api-key-Sr5NU9"

aws secretsmanager describe-secret `
  --secret-id $SecretArn `
  --region eu-west-3 `
  --query "{RotationEnabled:RotationEnabled,RotationRules:RotationRules,NextRotationDate:NextRotationDate,VersionIdsToStages:VersionIdsToStages}"
```

Check Lambda logs:

```powershell
aws logs tail "/aws/lambda/aiademo-bedrock-key-rotator" `
  --region eu-west-3 `
  --since 15m
```

Check ECS deployment state:

```powershell
aws ecs describe-services `
  --cluster aiademo-cluster `
  --services aiademo-voice-assistant-service `
  --region eu-west-3 `
  --query "services[0].{Desired:desiredCount,Running:runningCount,Pending:pendingCount,Deployments:deployments}"
```

Check application health:

```powershell
curl.exe -i "https://d2xxmkhm9bdfeq.cloudfront.net/demo5-voice-assistant/health"
```

## Notes

ECS injects Secrets Manager values only when a task starts. Because of that, the Lambda forces a new ECS deployment after a successful rotation.

The service currently runs one ECS task. During rotation, a short `503` window can happen while the task is replaced. For production-like usage, increase the desired count to `2` or tune ECS/ALB health-check settings.
