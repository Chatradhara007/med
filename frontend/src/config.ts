/**
 * Runtime configuration, read once from Vite's build-time environment.
 *
 * Every value here is a public identifier from the CloudFormation stack
 * outputs -- none of them is a secret, and no AWS access key ever belongs in
 * the browser: sign-in uses a Cognito token and uploads go to presigned S3
 * URLs precisely so the page never holds credentials.
 *
 * These are baked in at build time, so a missing variable cannot be noticed by
 * any later check -- it has to be caught here. Left unchecked, an empty pool id
 * makes Amplify throw `Auth UserPool not configured.` from the sign-in click
 * handler, where nothing is listening, and an empty API URL turns every request
 * into a same-origin path that the dev server happily answers with index.html.
 * Both look like "the app is broken" rather than "the app is unconfigured".
 */

interface ConfigField {
  key: string;
  value: string;
  output: string;
}

const read = (key: string): string => (import.meta.env[key] as string | undefined)?.trim() || '';

const FIELDS: ConfigField[] = [
  { key: 'VITE_AWS_REGION', value: read('VITE_AWS_REGION'), output: 'the stack region' },
  { key: 'VITE_COGNITO_USER_POOL_ID', value: read('VITE_COGNITO_USER_POOL_ID'), output: 'UserPoolId' },
  { key: 'VITE_COGNITO_USER_POOL_CLIENT_ID', value: read('VITE_COGNITO_USER_POOL_CLIENT_ID'), output: 'ClientId' },
  { key: 'VITE_COGNITO_DOMAIN', value: read('VITE_COGNITO_DOMAIN'), output: 'HostedUiUrl, without the https:// prefix' },
  { key: 'VITE_API_GATEWAY_URL', value: read('VITE_API_GATEWAY_URL'), output: 'ApiUrl' },
];

/** Variables that are required but absent or blank. Empty when fully configured. */
export const missingConfig: ConfigField[] = FIELDS.filter((f) => !f.value);

export const isConfigured = missingConfig.length === 0;

export const config = {
  region: read('VITE_AWS_REGION'),
  userPoolId: read('VITE_COGNITO_USER_POOL_ID'),
  userPoolClientId: read('VITE_COGNITO_USER_POOL_CLIENT_ID'),
  cognitoDomain: read('VITE_COGNITO_DOMAIN'),
  apiBaseUrl: read('VITE_API_GATEWAY_URL').replace(/\/$/, ''),
  /**
   * Cognito matches callback URLs exactly and the stack registers them with a
   * trailing slash, so sending a bare origin is rejected with
   * `redirect_mismatch`. Default to the origin plus a slash.
   */
  redirectUri: read('VITE_REDIRECT_URI') || `${window.location.origin}/`,
};
