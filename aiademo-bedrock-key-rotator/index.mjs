import { getTokenProvider } from "@aws/bedrock-token-generator";
import {
  DescribeSecretCommand,
  GetSecretValueCommand,
  PutSecretValueCommand,
  SecretsManagerClient,
  UpdateSecretVersionStageCommand,
} from "@aws-sdk/client-secrets-manager";
import {
  ECSClient,
  UpdateServiceCommand,
} from "@aws-sdk/client-ecs";

const REGION = process.env.REGION || process.env.AWS_REGION || "eu-west-3";
const SECRET_ID = process.env.SECRET_ID;
const ECS_CLUSTER = process.env.ECS_CLUSTER;
const ECS_SERVICE = process.env.ECS_SERVICE;

const SELF_TEST_MODEL_ID =
  process.env.SELF_TEST_MODEL_ID || "amazon.titan-embed-text-v2:0";

const KEY_EXPIRATION_SECONDS = Math.min(
  Number.parseInt(process.env.KEY_EXPIRATION_SECONDS || "21600", 10),
  43200,
);

const secretsManager = new SecretsManagerClient({ region: REGION });
const ecs = new ECSClient({ region: REGION });

const provideToken = getTokenProvider({
  region: REGION,
  expiresInSeconds: KEY_EXPIRATION_SECONDS,
});

function requireConfiguration() {
  const missing = [];

  if (!SECRET_ID) missing.push("SECRET_ID");
  if (!ECS_CLUSTER) missing.push("ECS_CLUSTER");
  if (!ECS_SERVICE) missing.push("ECS_SERVICE");

  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(", ")}`);
  }
}

async function describeSecret(secretId) {
  return secretsManager.send(
    new DescribeSecretCommand({
      SecretId: secretId,
    }),
  );
}

async function selfTestToken(token) {
  const encodedModelId = encodeURIComponent(SELF_TEST_MODEL_ID);

  const response = await fetch(
    `https://bedrock-runtime.${REGION}.amazonaws.com/model/${encodedModelId}/invoke`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        inputText: "Bedrock bearer token rotation self-test.",
        dimensions: 1024,
        normalize: true,
      }),
    },
  );

  const responseBody = await response.text();

  if (!response.ok) {
    throw new Error(
      `Bedrock token self-test failed: HTTP ${response.status} - ${responseBody.slice(0, 500)}`,
    );
  }

  console.log("Bedrock token self-test passed.");
}

async function createSecret(secretId, clientRequestToken) {
  try {
    await secretsManager.send(
      new GetSecretValueCommand({
        SecretId: secretId,
        VersionId: clientRequestToken,
        VersionStage: "AWSPENDING",
      }),
    );

    console.log("AWSPENDING secret value already exists.", {
      clientRequestToken,
    });

    return;
  } catch (error) {
    if (error.name !== "ResourceNotFoundException") {
      throw error;
    }

    console.log("AWSPENDING version ID exists without a value. Generating token.", {
      clientRequestToken,
    });
  }

  const newToken = await provideToken();

  // Validate before storing it.
  await selfTestToken(newToken);

  await secretsManager.send(
    new PutSecretValueCommand({
      SecretId: secretId,
      ClientRequestToken: clientRequestToken,
      SecretString: newToken,
      VersionStages: ["AWSPENDING"],
    }),
  );

  console.log("Created validated AWSPENDING secret value.", {
    clientRequestToken,
  });
}

async function setSecret() {
  // No external credential store must be updated.
  // The Bedrock bearer token is already valid after generation.
  console.log("setSecret completed: no external service update required.");
}

async function testSecret(secretId, clientRequestToken) {
  const pendingSecret = await secretsManager.send(
    new GetSecretValueCommand({
      SecretId: secretId,
      VersionId: clientRequestToken,
      VersionStage: "AWSPENDING",
    }),
  );

  if (!pendingSecret.SecretString) {
    throw new Error("The AWSPENDING secret version has no SecretString.");
  }

  await selfTestToken(pendingSecret.SecretString);

  console.log("AWSPENDING secret version passed validation.", {
    clientRequestToken,
  });
}

async function forceEcsDeployment() {
  await ecs.send(
    new UpdateServiceCommand({
      cluster: ECS_CLUSTER,
      service: ECS_SERVICE,
      forceNewDeployment: true,
    }),
  );

  console.log("Triggered ECS force-new-deployment.", {
    cluster: ECS_CLUSTER,
    service: ECS_SERVICE,
  });
}

async function finishSecret(secretId, clientRequestToken) {
  const metadata = await describeSecret(secretId);
  const versionStages = metadata.VersionIdsToStages || {};

  let currentVersionId = null;

  for (const [versionId, stages] of Object.entries(versionStages)) {
    if (stages.includes("AWSCURRENT")) {
      currentVersionId = versionId;
      break;
    }
  }

  if (currentVersionId !== clientRequestToken) {
    await secretsManager.send(
      new UpdateSecretVersionStageCommand({
        SecretId: secretId,
        VersionStage: "AWSCURRENT",
        MoveToVersionId: clientRequestToken,
        RemoveFromVersionId: currentVersionId || undefined,
      }),
    );

    console.log("Moved AWSCURRENT to the validated secret version.", {
      clientRequestToken,
      previousVersionId: currentVersionId,
    });
  } else {
    console.log("Secret version is already AWSCURRENT.", {
      clientRequestToken,
    });
  }

  // ECS reads the secret only when a new container starts.
  await forceEcsDeployment();
}

export const handler = async (event) => {
  requireConfiguration();

  const { SecretId, ClientRequestToken, Step } = event || {};

  if (!SecretId || !ClientRequestToken || !Step) {
    throw new Error(
      "Expected a Secrets Manager rotation event containing SecretId, ClientRequestToken, and Step.",
    );
  }

  if (SecretId !== SECRET_ID) {
    throw new Error(`Unexpected secret ID: ${SecretId}`);
  }

  console.log("Processing secret rotation step.", {
    secretId: SecretId,
    clientRequestToken: ClientRequestToken,
    step: Step,
    region: REGION,
  });

  switch (Step) {
    case "createSecret":
      await createSecret(SecretId, ClientRequestToken);
      break;

    case "setSecret":
      await setSecret();
      break;

    case "testSecret":
      await testSecret(SecretId, ClientRequestToken);
      break;

    case "finishSecret":
      await finishSecret(SecretId, ClientRequestToken);
      break;

    default:
      throw new Error(`Unsupported rotation step: ${Step}`);
  }

  return {
    status: "success",
    step: Step,
  };
};